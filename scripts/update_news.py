"""Fetch national weather headlines from Google News and write news.json.

Run by .github/workflows/news.yml every 30 minutes. Standard library only.
"""
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

QUERY = ('(tornado OR hurricane OR "tropical storm" OR "severe weather" OR "severe storms" OR flooding '
         'OR "flash flood" OR blizzard OR "winter storm" OR "heat wave" OR "National Weather Service" '
         'OR wildfire OR "ice storm" OR "storm damage") when:1d')
URL = 'https://news.google.com/rss/search?' + urllib.parse.urlencode(
    {'q': QUERY, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})

# Skip how-to, opinion, video and listicle filler; keep news.
SKIP = re.compile(r'\?|\b(live updates?|live:|watch|video|photos?|how to|what to know|opinion|'
                  r'quiz|deals?|sale|stock|shares|crypto|nfl|nba|mlb|ncaa|football|game|recipe|horoscope|'
                  r'movie|album|song|ranked|best places|tracker|live radar|maps?|waffle house)\b', re.IGNORECASE)
MAX_ITEMS = 9   # fills the 3-column grid evenly
MAX_AGE_H = 24


def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0 (NorthBamaWX news updater)'})
    root = None
    for attempt in range(2):        # short feed outages: retry once, then keep news.json
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                root = ET.fromstring(r.read())
            break
        except Exception as ex:
            print(f'News feed unavailable ({ex})')
            if attempt == 0:
                time.sleep(20)
    if root is None:
        print('Leaving news.json unchanged')
        return
    items, seen_titles, per_source = [], set(), {}
    now = time.time()
    for it in root.iter('item'):
        title = (it.findtext('title') or '').strip()
        source = (it.findtext('source') or '').strip()
        link = (it.findtext('link') or '').strip()
        try:
            ts = parsedate_to_datetime(it.findtext('pubDate')).timestamp()
        except Exception:
            continue
        if source and title.endswith(' - ' + source):
            title = title[: -len(' - ' + source)].strip()
        if not title or not source or not link.startswith('https://'):
            continue
        if now - ts > MAX_AGE_H * 3600 or SKIP.search(title) or len(title) > 160:
            continue
        key = re.sub(r'[^a-z0-9 ]', '', title.lower())[:60]
        if key in seen_titles or per_source.get(source, 0) >= 2:
            continue
        seen_titles.add(key)
        per_source[source] = per_source.get(source, 0) + 1
        items.append({'title': title, 'source': source, 'link': link, 'published': int(ts)})
    items.sort(key=lambda x: x['published'], reverse=True)
    items = items[:MAX_ITEMS]
    if not items:
        print('No headlines found; leaving news.json unchanged')
        return
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump({'updated': int(now), 'items': items}, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'Wrote {len(items)} headlines')


if __name__ == '__main__':
    main()
