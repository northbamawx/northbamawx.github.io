"""Fetch local data that browsers can't read directly (no CORS) and save it as
JSON for the page: pollen.json (Pollen.com, Huntsville) and roads.json
(ALDOT closures and incidents in our Alabama counties)."""
import json
import re
import urllib.request
from datetime import datetime, timezone

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
COUNTIES = {'Colbert', 'Cullman', 'DeKalb', 'Franklin', 'Jackson', 'Lauderdale', 'Lawrence',
            'Limestone', 'Madison', 'Marshall', 'Morgan'}
NOW = datetime.now(timezone.utc).isoformat(timespec='seconds')


def get(url, headers=None):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json', **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def save(name, data):
    with open(name, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write('\n')


def pollen():
    page = 'https://www.pollen.com/forecast/current/pollen/35801'
    d = get('https://www.pollen.com/api/forecast/current/pollen/35801', {'Referer': page})
    days = []
    for p in d['Location']['periods']:
        days.append({'day': p['Type'], 'index': p['Index'],
                     'triggers': [t['Name'] for t in p.get('Triggers', [])]})
    save('pollen.json', {'updated': NOW, 'city': 'Huntsville', 'days': days, 'source': page})


def roads():
    events = get('https://api.algotraffic.com/v4/TrafficEvents')
    out = []
    for e in events:
        loc = e.get('startLocation') or {}
        if loc.get('county') not in COUNTIES or not e.get('active', True):
            continue
        # Full closures of any kind, plus crashes, incidents and road conditions (flooding, ice, debris).
        if e.get('severity') != 'Closed' and e.get('type') not in ('Crash', 'Incident', 'RoadCondition'):
            continue
        # Rest areas/welcome centers and stalled cars aren't worth a viewer's attention.
        if e.get('type') == 'Facility' or re.search(r'abandoned|disabled vehicle', e.get('title') or '', re.I):
            continue
        out.append({
            'type': e.get('type'), 'severity': e.get('severity'), 'title': e.get('title'),
            'where': e.get('shortSubTitle') or e.get('subTitle'), 'detail': e.get('description'),
            'county': loc.get('county'), 'city': loc.get('city'),
            'lat': loc.get('latitude'), 'lon': loc.get('longitude'),
            'start': e.get('start'), 'end': e.get('end'), 'updated': e.get('lastUpdatedAt'),
        })
    rank = {'Crash': 0, 'RoadCondition': 1, 'Incident': 2}
    out.sort(key=lambda x: (x['severity'] != 'Closed', rank.get(x['type'], 3), x['county']))
    save('roads.json', {'updated': NOW, 'events': out})


COUNTY_UGC = {
    'ALC033': 'Colbert', 'ALC043': 'Cullman', 'ALC049': 'DeKalb', 'ALC059': 'Franklin', 'ALC071': 'Jackson',
    'ALC077': 'Lauderdale', 'ALC079': 'Lawrence', 'ALC083': 'Limestone', 'ALC089': 'Madison', 'ALC095': 'Marshall',
    'ALC103': 'Morgan', 'TNC051': 'Franklin TN', 'TNC055': 'Giles TN', 'TNC103': 'Lincoln TN', 'TNC127': 'Moore TN',
}
KINDS = {('TO', 'W'): 'tor', ('SV', 'W'): 'svr', ('FF', 'W'): 'ffw'}


def clock12(t):
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def archive():
    """Every day in the last year with a tornado, severe thunderstorm or flash
    flood warning in our counties (IEM's VTEC event lists for HUN and OHX)."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    tz = ZoneInfo('America/Chicago')
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=366)
    seen, days = set(), {}
    for wfo in ('HUN', 'OHX'):
        for year in sorted({cutoff.year, now.year}):
            data = get(f'https://mesonet.agron.iastate.edu/json/vtec_events_bywfo.py?wfo={wfo}&year={year}')
            for e in data.get('events', []):
                kind = KINDS.get((e.get('phenomena'), e.get('significance')))
                county = COUNTY_UGC.get(e.get('ugc'))
                if not kind or not county:
                    continue
                issued = datetime.fromisoformat(e['issue'].replace('Z', '+00:00'))
                if issued < cutoff:
                    continue
                date = issued.astimezone(tz).strftime('%Y-%m-%d')
                d = days.setdefault(date, {'date': date, 'tor': 0, 'svr': 0, 'ffw': 0, 'counties': set(), 'tornadoes': {}})
                d['counties'].add(county)
                key = (wfo, year, e['phenomena'], e['eventid'])
                if kind == 'tor':
                    t = d['tornadoes'].setdefault(key, {'url': e.get('url'), 'counties': [], 'time': clock12(issued.astimezone(tz))})
                    t['counties'].append(county)
                if key not in seen:
                    seen.add(key)
                    d[kind] += 1
    out = []
    for d in sorted(days.values(), key=lambda x: x['date'], reverse=True):
        d['counties'] = sorted(d['counties'])
        d['tornadoes'] = sorted(d['tornadoes'].values(), key=lambda t: t['url'] or '')
        out.append(d)
    save('archive.json', {'updated': NOW, 'days': out})


for job in (pollen, roads, archive):
    try:
        job()
        print(job.__name__, 'ok')
    except Exception as ex:   # keep the other file updating
        print(job.__name__, 'failed:', ex)
