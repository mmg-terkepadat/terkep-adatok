#!/usr/bin/env python3
"""Feladatlista a havi futáshoz: melyik Geofabrik-fájlból melyik kivonat készül.
Egy fájl egyszer töltődik le akkor is, ha több országot tartalmaz (pl. gcc-states)."""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
idx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'geofabrik-index.json', encoding='utf-8'))
urls = {f['properties']['id']: f['properties']['urls']['pbf'] for f in idx.get('features', []) if f.get('properties', {}).get('urls', {}).get('pbf')}
gmap = json.load(open(os.path.join(ROOT, 'data', 'geofabrik.json')))
world = json.load(open(os.path.join(ROOT, 'data', 'world.json'), encoding='utf-8'))


def url_for(cc):
    for gid in gmap.get(cc, []):
        if gid in urls:
            return urls[gid]
    return None


only = [x.strip().upper() for x in os.environ.get('ONLY', '').split(',') if x.strip()]
jobs = []
if not only or 'HU-DB' in only:
    jobs.append({'job': 'hu', 'cc': 'HU', 'url': url_for('HU')})
by_url = {}
for cc in sorted(world['cities']):
    if only and cc not in only:
        continue
    u = url_for(cc)
    if u:
        by_url.setdefault(u, []).append(cc)
    else:
        print(f'::warning::{cc}: nincs Geofabrik-kivonat', file=sys.stderr)
for u, ccs in by_url.items():
    jobs.append({'job': 'com', 'cc': ','.join(ccs), 'url': u})
print(f'{len(jobs)} feladat', file=sys.stderr)
print('matrix=' + json.dumps({'include': jobs}))
