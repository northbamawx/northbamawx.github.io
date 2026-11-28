"""Fetch LOCAL weather headlines (North Alabama & Southern Tennessee) from Google News and write news.json.

Run by .github/workflows/news.yml every 30 minutes. Standard library only.
Switched from national headlines to local on 2026-11-28 (the stream and site went local-only).
A headline is kept only if it is about weather AND names a place in our area (or comes from a
Huntsville TV station and is about weather). Quiet weather can mean few or no headlines; then
news.json is written with an empty list and the site says so (stale national items never linger).
"""
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

WEATHER = re.compile(
    r'\b(weather|storms?|tornado(es)?|severe|rain(fall|y)?|flood(s|ing)?|flash flood|snow|sleet|ice|icy|'
    r'freez(e|ing)|frost|cold|chill|wind(y|s)?|thunder(storms?)?|hail|heat|hot|drought|burn ban|fire danger|'
    r'forecast|temperatures?|national weather service|nws|power outages?|outages?|downed trees?|'
    r'damage|warning|watch|advisory|hurricane|tropical|fog|lightning|winter)\b', re.IGNORECASE)
PLACES = re.compile(
    r'\b(north alabama|n\. alabama|northern alabama|tennessee valley|huntsville|madison|decatur|athens|'
    r'florence|muscle shoals|the shoals|shoals|sheffield|tuscumbia|cullman|hartselle|guntersville|'
    r'scottsboro|albertville|boaz|arab|fort payne|rainsville|moulton|russellville|rogersville|'
    r'redstone|lake guntersville|wheeler lake|wilson lake|sand mountain|'
    r'(madison|limestone|morgan|marshall|jackson|dekalb|lauderdale|colbert|lawrence|franklin|cullman)'
    r' county|pulaski|lawrenceburg|fayetteville, tenn|tullahoma|lynchburg|winchester, tenn|'
    r'(giles|lincoln|moore|franklin) county, tenn|southern (middle )?tennessee|south(ern)? middle tennessee)\b',
    re.IGNORECASE)
# Local stations: their weather stories count even when the headline names no town.
LOCAL_SOURCES = re.compile(r'^(WHNT|WAAY|WAFF|Rocket City Now|WAFF 48|News 19|WAAY 31|WZDX|'
                           r'Times ?Daily|The Decatur Daily|Decatur Daily|The Cullman Times|Cullman Times|'
                           r'The Huntsville Times|Huntsville Business Journal|The Arab Tribune|'
                           r'The Advertiser-Gleam|Sand Mountain Reporter|The Daily Sentinel|'
                           r'Pulaski Citizen|Elk Valley Times|Lawrenceburg Now)', re.IGNORECASE)

QUERY = ('(weather OR storm OR tornado OR rain OR flooding OR snow OR freeze OR "National Weather Service") '
         '("North Alabama" OR Huntsville OR "Tennessee Valley" OR Decatur OR Shoals OR Cullman OR '
         'Guntersville OR Scottsboro OR Albertville OR Athens Alabama OR Madison Alabama OR Florence Alabama '
         'OR "Fort Payne" OR Pulaski Tennessee OR Lawrenceburg OR Tullahoma) when:3d')
URL = 'https://news.google.com/rss/search?' + urllib.parse.urlencode(
    {'q': QUERY, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})

# Skip how-to, opinion, video and listicle filler; keep news.
SKIP = re.compile(r'\?|\b(live updates?|live:|watch:|video|photos?|how to|what to know|opinion|'
                  r'quiz|deals?|sale|stock|shares|crypto|nfl|nba|mlb|ncaa|football|game|recipe|horoscope|'
                  r'movie|album|song|ranked|best places|tracker|live radar|maps?|waffle house|obituar(y|ies)|'
                  r'heat (beat|win|lose|loss)|miami heat|tour|concerts?|tickets|festival|parade)\b', re.IGNORECASE)
MAX_ITEMS = 9   # fills the 3-column grid evenly
MAX_AGE_H = 72  # local weather news is slower than national; keep 3 days


def is_local(title, source):
    if not WEATHER.search(title):
        return False
    return bool(PLACES.search(title) or LOCAL_SOURCES.search(source))


def main(out='news.json'):
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
        if not is_local(title, source):
            continue
        key = re.sub(r'[^a-z0-9 ]', '', title.lower())[:60]
        if key in seen_titles or per_source.get(source, 0) >= 3:
            continue
        seen_titles.add(key)
        per_source[source] = per_source.get(source, 0) + 1
        items.append({'title': title, 'source': source, 'link': link, 'published': int(ts)})
    items.sort(key=lambda x: x['published'], reverse=True)
    items = items[:MAX_ITEMS]
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'updated': int(now), 'local': True, 'items': items}, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'Wrote {len(items)} local headlines')


if __name__ == '__main__':
    import sys
    main(*sys.argv[1:2])
