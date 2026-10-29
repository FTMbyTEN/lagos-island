"""Model a real street, building by building, from OpenStreetMap: every building within reach of the street, at its
real footprint and height. Each one is written into the world's chunk files as a footprint building, with a look
(glass office, bank, church, mosque, shop house) from its OSM tags and name. The tiles under them are listed so the
game's generic towers and houses step aside.

  python tools/street_model.py <osm dir> "<street name>|<street name>..." <reach in metres>

The OSM dir holds lagos.json (roads) and bld*.json (buildings), as downloaded for tools/osm2world.py. Run it once per
street; streets already modelled are kept (web/map/streets.json lists them).
Map data (c) OpenStreetMap contributors, ODbL.
"""
import json, math, os, sys
os.environ.setdefault('OSM_TILE', '15')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osm2world as W  # (the same projection, simplification and storey height as the rest of the map)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
WEB = os.path.join(ROOT, 'web', 'map')

def look_of(t):
    n = (t.get('name') or '').lower(); k = t.get('building', 'yes'); a = t.get('amenity', ''); rel = t.get('religion', '')
    if k in ('church', 'cathedral', 'chapel') or (a == 'place_of_worship' and rel == 'christian') or 'cathedral' in n or 'church' in n: return 'church'
    if k == 'mosque' or 'mosque' in n or rel == 'muslim': return 'mosque'
    if any(w in n for w in ('bank', 'union', 'ecobank', 'zenith', 'sterling', 'first', 'uba', 'access', 'fidelity', 'wema')): return 'bank'
    if k in ('office', 'commercial') or t.get('office') or 'house' in n or 'tower' in n: return 'office'
    if k in ('retail', 'kiosk') or t.get('shop'): return 'shop'
    return 'block'

def main():
    osm, names, reach = sys.argv[1], [s.strip().lower() for s in sys.argv[2].split('|')], float(sys.argv[3])
    roads = json.load(open(os.path.join(osm, 'lagos.json'), encoding='utf-8'))['elements']
    ways = [e for e in roads if e['type'] == 'way' and e.get('tags', {}).get('name', '').lower() in names and e.get('geometry')]
    segs = [(W.wu(a['lat'], a['lon']), W.wu(b['lat'], b['lon'])) for w in ways for a, b in zip(w['geometry'], w['geometry'][1:])]
    print(len(ways), 'ways,', len(segs), 'segments of', names)
    def dist(x, z):
        best = 1e9
        for (ax, az), (bx, bz) in segs:
            dx, dz = bx - ax, bz - az; L = dx * dx + dz * dz or 1e-9; u = max(0, min(1, ((x - ax) * dx + (z - az) * dz) / L))
            best = min(best, math.hypot(ax + dx * u - x, az + dz * u - z))
        return best * W.U  # (metres)
    # the street's own road surface, so no building is placed standing in it
    def in_road(x, z): return dist(x, z) < 6
    out = []
    for f in sorted(os.listdir(osm)):
        if not (f.startswith('bld') and f.endswith('.json')): continue
        try: els = json.load(open(os.path.join(osm, f), encoding='utf-8')).get('elements', [])
        except ValueError: continue  # (a failed download)
        for e in els:
            if e['type'] != 'way' or len(e.get('geometry', [])) < 4: continue
            poly = [W.wu(p['lat'], p['lon']) for p in e['geometry']][:-1]
            if W.area(poly) * W.U * W.U < 25: continue
            cx = sum(p[0] for p in poly) / len(poly); cz = sum(p[1] for p in poly) / len(poly)
            if dist(cx, cz) > reach or in_road(cx, cz): continue
            t = e.get('tags', {}); lv = W.levels_of(t); look = look_of(t)
            if not lv: lv = {'office': 6, 'bank': 8, 'church': 4, 'mosque': 3, 'shop': 2}.get(look, 3)  # (untagged: a typical height for its kind on a busy island street)
            h = round(min(lv, 60) * W.LEVEL_M / W.HU, 1)
            out.append({'id': e['id'], 'poly': W.simplify(poly + [poly[0]], 0.35)[:-1], 'c': (cx, cz), 'h': h, 'look': look, 'name': t.get('name', '')})
    print(len(out), 'buildings,', sum(1 for b in out if b['name']), 'named')
    # into the chunks (a building goes to the chunk of its centre), the street's own buildings replacing any earlier run of it
    reg_f = os.path.join(WEB, 'streets.json'); reg = json.load(open(reg_f, encoding='utf-8')) if os.path.exists(reg_f) else {}
    key = names[0]; reg[key] = sorted(b['id'] for b in out); ids = {i for k, v in reg.items() if k != key for i in v}
    doc_f = os.path.join(WEB, 'lagos-world.js'); src = open(doc_f, encoding='utf-8').read(); head, body = src.split('window.LAGOS_BOARD = ', 1)
    doc = json.loads(body.rstrip().rstrip(';')); CH = doc['chunk']; q = lambda v: round(v * 10)
    cdir = os.path.join(WEB, 'world'); touched = 0
    for fn in os.listdir(cdir):  # (first take this street's earlier buildings out)
        p = os.path.join(cdir, fn); d = json.load(open(p, encoding='utf-8'))
        if d.get('bid') and any(i not in ids for i in d['bid']):
            keep = [k for k, i in enumerate(d['bid']) if i in ids]
            d['b'] = [d['b'][k] for k in keep]; d['bid'] = [d['bid'][k] for k in keep]; d['bl'] = [d['bl'][k] for k in keep]; d['bn'] = [d['bn'][k] for k in keep]
            open(p, 'w', encoding='utf-8').write(json.dumps(d, separators=(',', ':'), ensure_ascii=False))
    for b in out:
        ci, cj = int(b['c'][0] // (CH * 10)), int(b['c'][1] // (CH * 10)); p = os.path.join(cdir, f'{ci}_{cj}.json')
        d = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {'r': [], 'b': []}
        for k2 in ('bid', 'bl', 'bn'): d.setdefault(k2, [])
        if len(d['bid']) < len(d['b']): d['bid'] = [0] * (len(d['b']) - len(d['bid'])) + d['bid']; d['bl'] = [''] * (len(d['b']) - len(d['bl'])) + d['bl']; d['bn'] = [''] * (len(d['b']) - len(d['bn'])) + d['bn']
        d['b'].append([q(b['h'])] + [q(v) for pt in b['poly'] for v in pt]); d['bid'].append(b['id']); d['bl'].append(b['look']); d['bn'].append(b['name'])
        open(p, 'w', encoding='utf-8').write(json.dumps(d, separators=(',', ':'), ensure_ascii=False)); touched += 1
        if [ci, cj] not in doc['chunks']: doc['chunks'].append([ci, cj])
    # the tiles under every modelled building: the generic towers and houses keep off them
    fp = set(doc.get('fp', []))
    for b in out:
        xs = [p[0] for p in b['poly']]; zs = [p[1] for p in b['poly']]
        for j in range(int(min(zs) // 10), int(max(zs) // 10) + 1):
            for i in range(int(min(xs) // 10), int(max(xs) // 10) + 1): fp.add(j * doc['w'] + i)
    doc['fp'] = sorted(fp); doc.setdefault('streets', []); doc['streets'] = sorted(set(doc['streets']) | {key})
    open(doc_f, 'w', encoding='utf-8').write(head + 'window.LAGOS_BOARD = ' + json.dumps(doc, ensure_ascii=False, separators=(',', ':')) + ';\n')
    json.dump(reg, open(reg_f, 'w', encoding='utf-8'))
    print(touched, 'written;', len(fp), 'tiles kept clear')

if __name__ == '__main__': main()
