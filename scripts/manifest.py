#!/usr/bin/env python3
"""Az elkészült fájlok jegyzéke (manifest.json): a weboldalak ebből látják, mi friss, és ellenőrzik a letöltést."""
import glob, hashlib, json, os, sys, time

dist, old_path = sys.argv[1], sys.argv[2]
man = {'files': {}}
if os.path.exists(old_path):
    try:
        man = json.load(open(old_path))
    except Exception:
        pass
for f in sorted(glob.glob(os.path.join(dist, '*.gz'))):
    info = f + '.info.json'
    if not os.path.exists(info):
        continue  # a hibásnak jelölt kimenet nem kerül ki
    h = hashlib.sha256(open(f, 'rb').read()).hexdigest()
    man['files'][os.path.basename(f)] = dict(json.load(open(info)), sha256=h, size=os.path.getsize(f), built=int(time.time()))
man['generated'] = int(time.time())
man['source'] = 'OpenStreetMap (© OpenStreetMap contributors, ODbL) via Geofabrik'
json.dump(man, open(os.path.join(dist, 'manifest.json'), 'w'), indent=1)
print(len(man['files']), 'fájl a jegyzékben')
