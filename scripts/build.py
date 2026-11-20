#!/usr/bin/env python3
"""
Közérdekű helyek kigyűjtése egy OpenStreetMap-kivonatból (Geofabrik .osm.pbf).

  build.py hu  <input.pbf> <out_dir>      -> hu-poi.sqlite.gz  (a magyar oldal adatbázisa)
  build.py com <CC[,CC…]> <input.pbf> <out_dir> -> com-<CC>.jsonl.gz  (a nagyvárosok helyei egy országban)

A bemenetet előtte az osmium tags-filter szűri (lásd a workflow-t), így ez a lépés gyors.
Adat: © OpenStreetMap közreműködők, ODbL.
"""
import gzip, json, math, os, re, sqlite3, sys, time

import osmium

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def objects(path):
    """(típus, azonosító, tagek, lat, lon) – pont, vonal középpontja vagy multipoligon középpontja."""
    fp = osmium.FileProcessor(path).with_locations().with_areas()
    for o in fp:
        if o.is_node():
            if not o.location.valid():
                continue
            yield 'n', o.id, dict(o.tags), o.location.lat, o.location.lon
        elif o.is_way():
            la = [n.lat for n in o.nodes if n.location.valid()]
            lo = [n.lon for n in o.nodes if n.location.valid()]
            if la:
                # mint az Overpass „out center”: a befoglaló téglalap közepe
                yield 'w', o.id, dict(o.tags), (min(la) + max(la)) / 2, (min(lo) + max(lo)) / 2
        elif o.is_area():
            if o.from_way():
                continue  # a zárt vonalat már a way ágon kezeltük
            la, lo = [], []
            for ring in o.outer_rings():
                for n in ring:
                    if n.location.valid():
                        la.append(n.lat); lo.append(n.lon)
            if la:
                yield 'r', o.orig_id(), dict(o.tags), (min(la) + max(la)) / 2, (min(lo) + max(lo)) / 2


def cats_of(tags, categories):
    out = []
    for slug, filters in categories.items():
        for k, v in filters:
            if tags.get(k) == v:
                out.append(slug)
                break
    return out


def kind(t):
    if 'tower:type' in t:
        return 'observation'
    for k in ('amenity', 'shop', 'tourism', 'leisure', 'historic', 'natural'):
        if t.get(k):
            return t[k]
    return None


def ele(t):
    m = re.match(r'\s*(-?\d+)', str(t.get('ele', '')))
    return int(m.group(1)) if m else None


def cut(v, n=200):
    if v is None:
        return None
    v = str(v).strip()
    return v[:n] if v else None


def dist_m(la1, lo1, la2, lo2):
    p = math.pi / 180
    a = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- magyar oldal
def build_hu(pbf, out_dir):
    cfg = json.load(open(os.path.join(ROOT, 'data', 'hu.json'), encoding='utf-8'))
    cats, tiles = cfg['categories'], cfg['tiles']
    unnamed_ok = {'parkolo', 'jatszoter', 'bankautomata', 'kirandulas'}
    now = int(time.time())
    db_path = os.path.join(out_dir, 'hu-poi.sqlite')
    if os.path.exists(db_path):
        os.remove(db_path)
    db = sqlite3.connect(db_path)
    db.executescript('''
        CREATE TABLE poi (id TEXT NOT NULL, c TEXT NOT NULL, t TEXT NOT NULL, n TEXT, la REAL NOT NULL, lo REAL NOT NULL,
            st TEXT, city TEXT, h TEXT, ph TEXT, w TEXT, k TEXT, e INTEGER, seen INTEGER NOT NULL, PRIMARY KEY (id, c));
        CREATE INDEX poi_la ON poi (la);
        CREATE INDEX poi_tc ON poi (t, c);
        CREATE TABLE poi_jobs (t TEXT NOT NULL, c TEXT NOT NULL, fetched INTEGER NOT NULL DEFAULT 0, n INTEGER NOT NULL DEFAULT 0,
            tried INTEGER NOT NULL DEFAULT 0, err TEXT, PRIMARY KEY (t, c));
    ''')
    count = {}
    rows = 0
    for typ, oid, t, la, lo in objects(pbf):
        tile = next((k for k, (s, w, n, e) in tiles.items() if s <= la < n and w <= lo < e), None)
        if not tile:
            continue
        for c in cats_of(t, cats):
            name = t.get('name') or t.get('brand') or t.get('operator')
            if not name and c not in unnamed_ok:
                continue
            if not name and c == 'kirandulas' and t.get('natural') == 'peak':
                continue
            web = t.get('website') or t.get('contact:website') or ''
            st = ' '.join(x for x in (t.get('addr:street'), t.get('addr:housenumber')) if x)
            db.execute('INSERT OR REPLACE INTO poi VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                typ + str(oid), c, tile, cut(name), round(la, 6), round(lo, 6), cut(st), cut(t.get('addr:city'), 80),
                cut(t.get('opening_hours')), cut(t.get('phone') or t.get('contact:phone'), 80),
                cut(web, 300) if re.match(r'^https?://', web, re.I) else None, kind(t), ele(t), now))
            count[(tile, c)] = count.get((tile, c), 0) + 1
            rows += 1
    for tile in tiles:
        for c in cats:
            db.execute('INSERT INTO poi_jobs (t, c, fetched, n, tried, err) VALUES (?,?,?,?,?,NULL)', (tile, c, now, count.get((tile, c), 0), now))
    db.commit()
    db.execute('VACUUM')
    db.close()
    with open(db_path, 'rb') as f, gzip.open(db_path + '.gz', 'wb', 9) as g:
        g.write(f.read())
    os.remove(db_path)
    print(f'hu: {rows} sor')
    if rows < 20000:
        sys.exit(f'Túl kevés hely ({rows}) – valószínűleg hibás bemenet, nem tesszük közzé.')
    json.dump({'rows': rows}, open(os.path.join(out_dir, 'hu-poi.sqlite.gz.info.json'), 'w'))


# ---------------------------------------------------------------- külföldi oldal
def build_com(cc, pbf, out_dir):
    cfg = json.load(open(os.path.join(ROOT, 'data', 'world.json'), encoding='utf-8'))
    cats = cfg['categories']
    cities = cfg['cities'].get(cc, [])
    if not cities:
        print(f'::warning::{cc}: nincs város a listában')
        return
    unnamed_ok = {'parking', 'playgrounds', 'atms', 'outdoors'}
    # rácsos index: 0,1 fokos cellák -> a környező városok
    grid = {}
    for i, (key, name, la, lo, r) in enumerate(cities):
        dla = r / 111320 + 0.01
        dlo = r / (111320 * max(0.2, math.cos(math.radians(la)))) + 0.01
        for gy in range(math.floor((la - dla) * 10), math.floor((la + dla) * 10) + 1):
            for gx in range(math.floor((lo - dlo) * 10), math.floor((lo + dlo) * 10) + 1):
                grid.setdefault((gy, gx), []).append(i)
    found = [[] for _ in cities]
    for typ, oid, t, la, lo in objects(pbf):
        near = grid.get((math.floor(la * 10), math.floor(lo * 10)))
        if not near:
            continue
        cs = cats_of(t, cats)
        if not cs:
            continue
        c = cs[0]
        name = t.get('name') or t.get('brand') or t.get('operator')
        if not name and c not in unnamed_ok:
            continue
        if not name and c == 'outdoors' and t.get('natural') == 'peak':
            continue
        for i in near:
            key, cname, cla, clo, r = cities[i]
            d = dist_m(cla, clo, la, lo)
            if d > r:
                continue
            addr = ' '.join(x for x in (t.get('addr:street'), t.get('addr:housenumber')) if x).strip()
            if addr and t.get('addr:city') and t.get('addr:city') != cname:
                addr = t['addr:city'] + ', ' + addr
            item = {'c': c, 'n': name, 'la': round(la, 6), 'lo': round(lo, 6), 'a': addr or None,
                    'h': t.get('opening_hours'), 'ph': t.get('phone') or t.get('contact:phone'),
                    'w': t.get('website') or t.get('contact:website'), 'k': kind(t), 'e': ele(t), 'o': typ + str(oid)}
            found[i].append((d, {k: v for k, v in item.items() if v not in (None, '')}))
    out = os.path.join(out_dir, f'com-{cc}.jsonl.gz')
    total = 0
    # soronként egy város (JSON Lines): a weboldal így kevés memóriával, soronként tudja beolvasni
    with gzip.open(out, 'wt', encoding='utf-8', compresslevel=9) as g:
        for i, (key, name, la, lo, r) in enumerate(cities):
            # kategóriánként a legközelebbi 150, összesen legfeljebb 1500 (mint az élő lekérdezésnél)
            per = {}
            for d, it in sorted(found[i], key=lambda x: x[0]):
                lst = per.setdefault(it['c'], [])
                if len(lst) < 150:
                    lst.append((d, it))
            items = [it for d, it in sorted((x for l in per.values() for x in l), key=lambda x: x[0])][:1500]
            g.write(json.dumps({'k': key, 'radius': r, 'items': items}, ensure_ascii=False, separators=(',', ':')) + '\n')
            total += len(items)
    places = cities
    print(f'{cc}: {len(places)} város, {total} hely')
    if total == 0:
        print(f'::warning::{cc}: egy hely sincs – valószínűleg hibás bemenet, nem tesszük közzé.')
        return
    json.dump({'places': len(places), 'rows': total}, open(out + '.info.json', 'w'))


if __name__ == '__main__':
    if sys.argv[1] == 'hu':
        build_hu(sys.argv[2], sys.argv[3])
    else:
        # több ország is jöhet egy fájlból (pl. gcc-states): vesszővel elválasztva
        for cc in sys.argv[2].split(','):
            build_com(cc, sys.argv[3], sys.argv[4])
