"""Fetch the channel's newest uploads from YouTube's public RSS feed and write
videos.json. Run by .github/workflows/news.yml alongside the news update.
Standard library only; no API key or quota."""
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

CHANNEL_ID = 'UC4nij4NgHjDJ8i5tv-1wWIA'
URL = f'https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}'
NS = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015',
      'm': 'http://search.yahoo.com/mrss/'}
MAX_ITEMS = 8
# The 24/7 stream itself shows at the top of the page; leave it out here.
SKIP = re.compile(r'24/7|\blive\b', re.IGNORECASE)


def main():
    # YouTube's feed has short outages (404/500, seen overnight 2026-10-12). Retry once,
    # then keep the current videos.json instead of failing the whole workflow.
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0 (NorthBamaWX video updater)'})
    root = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                root = ET.fromstring(r.read())
            break
        except Exception as ex:
            print(f'YouTube feed unavailable ({ex})')
            if attempt == 0:
                time.sleep(20)
    if root is None:
        print('Leaving videos.json unchanged')
        return
    items, seen = [], set()
    for e in root.findall('a:entry', NS):
        vid = e.findtext('yt:videoId', namespaces=NS)
        title = (e.findtext('a:title', namespaces=NS) or '').strip()
        link = e.find('a:link', NS).get('href', '')
        if not vid or SKIP.search(title):
            continue
        # Each alert clip is uploaded twice (Short + regular video) with the
        # same title; the feed is newest-first and the Short comes first.
        key = re.sub(r'\s*#Shorts\s*$', '', title, flags=re.IGNORECASE).lower()
        if key in seen:
            continue
        seen.add(key)
        published = datetime.fromisoformat(e.findtext('a:published', namespaces=NS)).timestamp()
        items.append({
            'id': vid,
            'title': re.sub(r'\s*#Shorts\s*$', '', title, flags=re.IGNORECASE),
            'short': '/shorts/' in link,
            'published': int(published),
        })
        if len(items) >= MAX_ITEMS:
            break
    if not items:
        print('No videos found; leaving videos.json unchanged')
        return
    with open('videos.json', 'w', encoding='utf-8') as f:
        json.dump({'updated': int(time.time()), 'items': items}, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'Wrote {len(items)} videos')


if __name__ == '__main__':
    main()
