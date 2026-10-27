# Lagos from OpenStreetMap at the people's scale, for the game's world. A person is 1.8 units tall, so a unit is a metre
# upright: buildings stand their real height and streets are their real width. Across the ground the city is drawn at
# 1.5 m a unit (a 15 m tile = 10 units), squeezed a little the way GTA squeezes its cities, so the landmarks' models,
# built to the tile, keep their size.
# Builds the 30 m board with tools/osm2board.py (land, water, the drivable roads, the places on their real sites) and
# adds what the board can't hold: every street as its real line at its real width, and every building as its real
# footprint and height, cut into chunks the game loads round the player. Map data (c) OpenStreetMap contributors, ODbL.
#   python -I tools/osm2world.py <roads.json> <marks.json> <waters.json> <out dir> <buildings.json>...
import os, sys, json, math, collections
os.environ['OSM_TILE'] = '15'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osm2board as B

U = 1.5                        # metres a world unit across the ground
HU = 1.0                       # metres a world unit upright (people scale)
WU = 1.25                      # metres a world unit across a street (between the two: streets their real width beside the buildings)
CH = 48                        # tiles a chunk side (1.44 km)
WIDTH = {'motorway': 24, 'trunk': 20, 'primary': 16, 'secondary': 13, 'tertiary': 10, 'residential': 7, 'unclassified': 7, 'living_street': 6}  # metres, kerb to kerb
CLS = {k: n for n, k in enumerate(WIDTH)}
LEVEL_M = 3.2
DEFAULT_LEVELS = {'lagos': 3, 'ikoyi': 2, 'banana': 3, 'vi': 4, 'atlantic': 8, 'lekki': 2, 'ajah': 2, 'hqrow': 2, 'nml': 2}

def wu(lat, lon): return ((lon - B.LON0) * B.MX / U, (B.LAT1 - lat) * B.MY / U)

def simplify(pts, eps):  # Douglas-Peucker
    if len(pts) < 3: return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]; dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy) or 1e-9
    k, dm = 0, -1
    for n in range(1, len(pts) - 1):
        d = abs(dy * pts[n][0] - dx * pts[n][1] + x1 * y0 - y1 * x0) / L if L > 1e-6 else math.hypot(pts[n][0] - x0, pts[n][1] - y0)
        if d > dm: k, dm = n, d
    if dm <= eps: return [pts[0], pts[-1]]
    return simplify(pts[:k + 1], eps)[:-1] + simplify(pts[k:], eps)

def area(poly): return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2

def levels_of(t):
    for k in ('building:levels', 'levels'):
        try: return max(1, float(t[k].split(';')[0]))
        except Exception: pass
    try: return max(1, float(t['height'].replace('m', '').strip()) / LEVEL_M)
    except Exception: return None

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

def nt_register():
    # the New Town register the game server holds (server/lib/island/island_newtown.dart): [id, tower (1) or block (0),
    # rooms], in its order. The game gives these ids to the real map's towers and blocks, so every flat already bought
    # or allocated keeps its building
    import re
    s = open(os.path.join(ROOT, 'server', 'lib', 'island', 'island_newtown.dart'), encoding='utf-8').read()
    return [[m.group(1), 1 if m.group(2) == 'true' else 0, int(m.group(3))] for m in re.finditer(r"'(nt\d+)': \(tower: (true|false), rooms: (\d+)\)", s)]

def write_stops(gp, sites):
    # the server's stops (shifts and paid gigs check you reached them): each at its place's front door on this map, so
    # the server and the map always agree. Which place each stop is: tools/stop_places.json
    table = json.load(open(os.path.join(ROOT, 'tools', 'stop_places.json'), encoding='utf-8'))
    size = {p['name']: (p['w'], p['h']) for p in gp}
    f = os.path.join(ROOT, 'server', 'lib', 'island', 'island_stops.dart'); s = open(f, encoding='utf-8').read()  # (its CRLF line endings come in as plain newlines, and go back out as CRLF)
    a = s.index('const islandStops = '); b = s.index('};', a) + 2
    q = lambda t: '"' + t + '"' if "'" in t else "'" + t + "'"
    lines = []
    for t in table:
        i, j = sites[t['place']]; w, h = size[t['place']]
        lines.append(f"  '{t['key']}': (name: {q(t['name'])}, kind: '{t['kind']}', x: {(i + w / 2) * 10:.1f}, z: {(j + h) * 10 + 3:.1f}),")
    s = s[:a] + 'const islandStops = <String, ({String name, String kind, double x, double z})>{\n' + '\n'.join(lines) + '\n};' + s[b:]
    open(f, 'w', encoding='utf-8', newline='\r\n').write(s)

def main():
    roads_f, marks_f, waters_f, out_dir, *bld_fs = sys.argv[1:]
    load = lambda f: json.load(open(f, encoding='utf-8'))
    roads, marks, waters = load(roads_f), load(marks_f), load(waters_f)
    blds = []
    for f in bld_fs:
        for e in load(f).get('elements', []):
            if e['type'] != 'way' or 'geometry' not in e or len(e['geometry']) < 4: continue
            poly = [wu(p['lat'], p['lon']) for p in e['geometry']][:-1]
            if area(poly) * U * U < 25: continue  # (sheds and kiosks under 25 square metres)
            cx = sum(p[0] for p in poly) / len(poly); cz = sum(p[1] for p in poly) / len(poly)
            blds.append({'poly': simplify(poly + [poly[0]], 0.35)[:-1], 'c': (cx, cz), 'lv': levels_of(e.get('tags', {})), 'kind': e.get('tags', {}).get('building', 'yes')})
    print(len(blds), 'buildings')
    tile, rank, name, lm = B.build(roads, marks, waters, blds=[(b['c'][0] / 10, b['c'][1] / 10) for b in blds])
    html = open(os.path.join(out_dir, '..', 'index.html'), encoding='utf-8').read()
    gp = B.game_places(html); sites = B.place_all(tile, rank, gp); write_stops(gp, sites)
    W, H = B.W, B.H
    for j in range(H):
        for i in range(W):
            if tile[j][i] not in (B.ROAD, B.BRIDGE): rank[j][i] = 0
    dist = B.districts()
    def district(i, j):
        for d in dist:
            r = d['rect']
            if r[0] <= i <= r[2] and r[1] <= j <= r[3]: return d['id']
        return 'lekki'
    # the places claim their ground: no real building stands inside a landmark's footprint
    claimed = set()
    for p in gp:
        if p['name'] in sites:
            i0, j0 = sites[p['name']]
            for j in range(j0, j0 + p['h']):
                for i in range(i0, i0 + p['w']): claimed.add((i, j))
    keep = []
    for b in blds:
        i, j = int(b['c'][0] // 10), int(b['c'][1] // 10)
        if not (0 <= i < W and 0 <= j < H) or tile[j][i] == B.W0 or (i, j) in claimed: continue  # (the squares are coarse: a real building is kept even where a road's square takes in its plot)
        lv = b['lv'] or DEFAULT_LEVELS.get(district(i, j), 2)
        if b['kind'] in ('commercial', 'office', 'retail', 'hotel') and not b['lv']: lv = max(lv, 4)
        b['h'] = round(min(lv, 60) * LEVEL_M / HU, 1); keep.append(b)
    print(len(keep), 'buildings kept')
    # the streets: every real one, at its width, plus the joining roads the board added (tile to tile)
    lines = []
    for e in roads['elements']:
        t = e.get('tags', {}); hw = t.get('highway', '').replace('_link', '')
        if e['type'] != 'way' or 'geometry' not in e or hw not in WIDTH: continue
        pts = [wu(p['lat'], p['lon']) for p in e['geometry']]
        if all(not (0 <= int(x // 10) < W and 0 <= int(z // 10) < H) or tile[int(z // 10)][int(x // 10)] == B.W0 for x, z in pts) and t.get('bridge') != 'yes': continue
        if any((int(x // 10), int(z // 10)) in claimed for x, z in pts[1:-1]): continue  # (a street under a landmark is its forecourt now)
        lines.append([CLS[hw], 1 if t.get('bridge') == 'yes' else 0, simplify(pts, 0.4)])
    drawn = set()
    for cls, br, pts in lines:
        for i, j in B.cells([(x / 10, z / 10) for x, z in pts]): drawn.add((i, j))
    added = {(i, j) for j in range(H) for i in range(W) if tile[j][i] in (B.ROAD, B.BRIDGE) and (i, j) not in drawn and not any((i + di, j + dj) in drawn for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj)}
    for i, j in added:
        for di, dj in ((1, 0), (0, 1)):
            n = (i + di, j + dj)
            if n in added or (0 <= n[0] < W and 0 <= n[1] < H and tile[n[1]][n[0]] in (B.ROAD, B.BRIDGE)):
                lines.append([CLS['residential'], 1 if tile[j][i] == B.BRIDGE else 0, [(i * 10 + 5, j * 10 + 5), (n[0] * 10 + 5, n[1] * 10 + 5)]])
    # the streets as drawn (each at its width with its pavement), by tile, to test buildings and lots against
    hwid = [WIDTH[k] / WU / 2 + 0.9 for k in WIDTH]; segs = collections.defaultdict(list)
    for cls, br, pts in lines:
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            hw = hwid[cls]
            for tj in range(int((min(az, bz) - hw) // 10), int((max(az, bz) + hw) // 10) + 1):
                for ti in range(int((min(ax, bx) - hw) // 10), int((max(ax, bx) + hw) // 10) + 1): segs[(ti, tj)].append((ax, az, bx, bz, hw))
    def seg_d(px, pz, ax, az, bx, bz):
        dx, dz = bx - ax, bz - az; L2 = dx * dx + dz * dz or 1e-9; t = max(0, min(1, ((px - ax) * dx + (pz - az) * dz) / L2))
        return math.hypot(px - ax - dx * t, pz - az - dz * t)
    def inside(poly, x, z):
        c = False
        for (ax, az), (bx, bz) in zip(poly, poly[1:] + poly[:1]):
            if (az > z) != (bz > z) and x < ax + (z - az) * (bx - ax) / (bz - az): c = not c
        return c
    def on_road(poly):  # a building that a street, drawn at its width, runs into
        xs = [p[0] for p in poly]; zs = [p[1] for p in poly]; near = set()
        for tj in range(int(min(zs) // 10) - 1, int(max(zs) // 10) + 2):
            for ti in range(int(min(xs) // 10) - 1, int(max(xs) // 10) + 2): near.update(segs.get((ti, tj), ()))
        for ax, az, bx, bz, hw in near:
            if any(seg_d(px, pz, ax, az, bx, bz) < hw for px, pz in poly): return True  # (a corner in the street)
            L = math.hypot(bx - ax, bz - az); n = max(1, int(L / 1.5))
            for k in range(n + 1):  # (the street's own line through the building, or passing within its width of a wall)
                sx, sz = ax + (bx - ax) * k / n, az + (bz - az) * k / n
                if inside(poly, sx, sz) or any(seg_d(sx, sz, p[0], p[1], q[0], q[1]) < hw * 0.8 for p, q in zip(poly, poly[1:] + poly[:1])): return True
        return False
    before = len(keep); keep = [b for b in keep if not on_road(b['poly'])]; print(before - len(keep), 'buildings left out for standing in a street')
    # the squares a street (or its pavement) reaches into: no modelled house, tree or lot is put on them
    rmask = [[0] * W for _ in range(H)]
    for (ti, tj), L in segs.items():
        if 0 <= ti < W and 0 <= tj < H and any(seg_d(ti * 10 + 5, tj * 10 + 5, *s[:4]) < s[4] + 4.6 for s in L): rmask[tj][ti] = 1
    # the low buildings (one or two floors) become the island's own modelled houses, one to a square: a Brazilian house
    # in old Lagos, a district home elsewhere. The taller ones keep their real footprints and heights
    hmask = [[0] * W for _ in range(H)]; tall = []
    for b in keep:
        i, j = int(b['c'][0] // 10), int(b['c'][1] // 10)
        if b['h'] <= 2 * LEVEL_M / HU + 0.1 and not rmask[j][i]: hmask[j][i] = 1
        else: tall.append(b)
    for b in tall:  # (no house where a tall one stands)
        for jj in range(int(min(p[1] for p in b['poly']) // 10), int(max(p[1] for p in b['poly']) // 10) + 1):
            for ii in range(int(min(p[0] for p in b['poly']) // 10), int(max(p[0] for p in b['poly']) // 10) + 1):
                if 0 <= ii < W and 0 <= jj < H: hmask[jj][ii] = 0
    # ...and the tall ones become the island's modelled towers and office blocks on their squares (no plain blocks):
    # tmask 1 a block (up to six floors), 2 a tower
    tmask = [[0] * W for _ in range(H)]
    for b in tall:
        i, j = int(b['c'][0] // 10), int(b['c'][1] // 10)
        if 0 <= i < W and 0 <= j < H and not rmask[j][i]: tmask[j][i] = max(tmask[j][i], 2 if b['h'] > 6 * LEVEL_M / HU else 1); hmask[j][i] = 0
    print(len(keep) - len(tall), 'low buildings become', sum(map(sum, hmask)), 'modelled houses;', len(tall), 'tall ones become', sum(1 for r in tmask for v in r if v), 'modelled towers and blocks')
    keep = []
    # the chunks
    cw, chh = (W + CH - 1) // CH, (H + CH - 1) // CH
    chunks = collections.defaultdict(lambda: {'r': [], 'b': []})
    q = lambda v: round(v * 10)  # (tenths of a unit)
    for cls, br, pts in lines:
        xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
        for cj in range(max(0, int(min(zs) // (CH * 10))), min(chh, int(max(zs) // (CH * 10)) + 1)):
            for ci in range(max(0, int(min(xs) // (CH * 10))), min(cw, int(max(xs) // (CH * 10)) + 1)):
                chunks[(ci, cj)]['r'].append([cls, br] + [q(v) for p in pts for v in p])
    for b in keep:
        ci, cj = int(b['c'][0] // (CH * 10)), int(b['c'][1] // (CH * 10))
        chunks[(ci, cj)]['b'].append([q(b['h'])] + [q(v) for p in b['poly'] for v in p])
    cdir = os.path.join(out_dir, 'world'); os.makedirs(cdir, exist_ok=True)
    for f in os.listdir(cdir):
        if f.endswith('.json'): os.remove(os.path.join(cdir, f))
    total = 0
    for (ci, cj), c in chunks.items():
        s = json.dumps(c, separators=(',', ':')); total += len(s)
        open(os.path.join(cdir, f'{ci}_{cj}.json'), 'w', encoding='utf-8').write(s)
    # which tiles a building stands on (its middle, and every tile whose centre it covers): no tree or lot is put there
    bt = [[0] * W for _ in range(H)]
    def inside(poly, x, z):
        c = False
        for (ax, az), (bx, bz) in zip(poly, poly[1:] + poly[:1]):
            if (az > z) != (bz > z) and x < ax + (z - az) * (bx - ax) / (bz - az): c = not c
        return c
    for b in keep:
        i, j = int(b['c'][0] // 10), int(b['c'][1] // 10); bt[j][i] = 1
        xs = [p[0] for p in b['poly']]; zs = [p[1] for p in b['poly']]
        for jj in range(int(min(zs) // 10), int(max(zs) // 10) + 1):
            for ii in range(int(min(xs) // 10), int(max(xs) // 10) + 1):
                if 0 <= ii < W and 0 <= jj < H and inside(b['poly'], ii * 10 + 5, jj * 10 + 5): bt[jj][ii] = 1
    def rle_of(grid):
        out_rows = []
        for row in grid:
            out, k = [], 0
            while k < W:
                e = k
                while e + 1 < W and row[e + 1] == row[k]: e += 1
                out.append(f'{row[k]}{e - k + 1:x}'); k = e + 1
            out_rows.append(','.join(out))
        return out_rows
    # the board: each row run-length coded ("<code><count>" pairs, count in hex, comma between)
    rle = rle_of(tile)
    doc = {'attribution': '© OpenStreetMap contributors (ODbL)', 'w': W, 'h': H, 'tile_m': B.TILE, 'unit_m': U, 'chunk': CH, 'chunks': [list(k) for k in sorted(chunks)],
           'widths': [WIDTH[k] / WU for k in WIDTH], 'ntReg': nt_register(), 'rle': rle, 'brle': rle_of(bt), 'rrle': rle_of(rmask), 'hrle': rle_of(hmask), 'trle': rle_of(tmask), 'places': sites, 'districts': dist}
    open(os.path.join(out_dir, 'lagos-world.js'), 'w', encoding='utf-8').write('// Lagos at true scale, made by tools/osm2world.py. Map data (c) OpenStreetMap contributors, ODbL.\nwindow.LAGOS_BOARD = ' + json.dumps(doc, ensure_ascii=False, separators=(',', ':')) + ';\n')
    c = collections.Counter(ch for row in tile for ch in row)
    print(f'{W}x{H} tiles', dict(c), len(lines), 'street lines', len(chunks), 'chunks', round(total / 1e6, 1), 'MB of chunks', os.path.getsize(os.path.join(out_dir, 'lagos-world.js')) // 1000, 'KB board')

if __name__ == '__main__':
    main()
