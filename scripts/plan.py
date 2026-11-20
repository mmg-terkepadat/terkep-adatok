#!/usr/bin/env python3
"""Feladatlista a havi futáshoz: melyik Geofabrik-fájlból melyik kivonat készül."""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# a jegyzéket a workflow tölti le curl-lel (megbízhatóbb, IPv4-en)
idx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'geofabrik-index.json', encoding='utf-8'))
feats = [f['properties'] for f in idx['features'] if f['properties'].get('urls', {}).get('pbf')]


def url_for(cc):
    cand = [p for p in feats if cc in (p.get('iso3166-1:alpha2') or [])]
    if not cand:
        return None
    ids = {p['id'] for p in cand}
    # az egész országot lefedő fájl: nem tartományi (iso3166-2), és nem egy másik jelölt része
    cand.sort(key=lambda p: (len(p.get('iso3166-1:alpha2') or []), 'iso3166-2' in p, p.get('parent') in ids))
    return cand[0]['urls']['pbf']


world = json.load(open(os.path.join(ROOT, 'data', 'world.json'), encoding='utf-8'))
only = [x.strip().upper() for x in os.environ.get('ONLY', '').split(',') if x.strip()]
jobs = []
if not only or 'HU-DB' in only:
    jobs.append({'job': 'hu', 'cc': 'HU', 'url': url_for('HU')})
for cc in sorted(world['cities']):
    if only and cc not in only:
        continue
    u = url_for(cc)
    if u:
        jobs.append({'job': 'com', 'cc': cc, 'url': u})
    else:
        print(f'::warning::{cc}: nincs Geofabrik-kivonat', file=sys.stderr)
print('matrix=' + json.dumps({'include': jobs}))
