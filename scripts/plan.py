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

# Napi pótlás (STALE=1): csak a hiányzó vagy a legutóbbi futásból kimaradt fájlok – így egy elakadt
# letöltés másnap magától újrapróbálkozik, és nem kell kézzel indítani semmit.
if os.environ.get('STALE') == '1':
    import time, urllib.request
    try:
        man = json.load(urllib.request.urlopen(os.environ['MANIFEST_URL'], timeout=60)).get('files', {})
    except Exception as e:
        print(f'::warning::manifest nem olvasható ({e}) – nincs pótlás', file=sys.stderr)
        print('matrix=' + json.dumps({'include': []})); print('count=0'); sys.exit(0)
    # „elmaradt”: hiányzik, vagy 2 nappal régebbi a legutóbbi futás legfrissebb fájljánál
    old = max([v.get('built', 0) for v in man.values()] or [time.time()]) - 2 * 86400
    stale = lambda name: name not in man or man[name].get('built', 0) < old
    only = [cc for cc in world['cities'] if stale(f'com-{cc}.jsonl.gz')]
    if stale('hu-poi.sqlite.gz'):
        only.append('HU-DB')
    if not only:
        print('Minden fájl friss, nincs mit pótolni.', file=sys.stderr)
        print('matrix=' + json.dumps({'include': []})); print('count=0'); sys.exit(0)
    print('Pótlás: ' + ','.join(only), file=sys.stderr)
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
print(f'count={len(jobs)}')
