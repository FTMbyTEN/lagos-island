# Lagos from OpenStreetMap to the game's board.
# Reads an Overpass dump (roads, coastline) and a landmark dump, writes web/map/lagos-board.json:
# a grid of 100 m tiles (0 water, 1 land, 2 sand, 3 road, 4 bridge), the name of the road on each road tile,
# and the real landmarks placed on their tiles. Map data (c) OpenStreetMap contributors, ODbL.
#   python -I tools/osm2board.py <roads.json> <marks.json> <out.json> [preview.png] [waters.json]
import json, math, os, sys, collections

LON0, LON1, LAT0, LAT1 = 3.37, 3.60, 6.395, 6.48
TILE = float(os.environ.get('OSM_TILE', '100'))  # metres a tile: 100 for the overview board, 30 for the true-scale world (a game tile is 30 m)
SC = 100.0 / TILE  # (how many of these tiles to the old 100 m one)
MX = 111320 * math.cos(math.radians((LAT0 + LAT1) / 2)); MY = 110574
W, H = round((LON1 - LON0) * MX / TILE), round((LAT1 - LAT0) * MY / TILE)
W0, LAND, SAND, ROAD, BRIDGE = 0, 1, 2, 3, 4
RANK = {'motorway': 5, 'trunk': 4, 'primary': 3, 'secondary': 2, 'tertiary': 1}

def ij(lat, lon): return ((lon - LON0) * MX / TILE, (LAT1 - lat) * MY / TILE)
def cells(pts):  # every tile a polyline passes through, sampled every quarter tile
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) * 4))
        for k in range(n + 1):
            i, j = int(x0 + (x1 - x0) * k / n), int(y0 + (y1 - y0) * k / n)
            if not (0 <= i < W and 0 <= j < H) or (out and out[-1] == (i, j)): continue
            if out and out[-1][0] != i and out[-1][1] != j: out.append((i, out[-1][1]))  # (a diagonal step goes round the corner: roads join side to side)
            out.append((i, j))
    return out
def length(pts): return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))

CUTS = {'MacGregor Canal': 1, 'Five Cowries Creek': 1, 'Kuramo Creek': 0, 'Lagos Harbour': 1, 'Commodore Channel': 1, 'Ebute Metta Creek': 1, 'Lighthouse Creek': 0, 'Badagry Creek': 1}  # half-widths in tiles
if TILE < 100: CUTS = {'MacGregor Canal': 1, 'Five Cowries Creek': 2, 'Kuramo Creek': 0, 'Lagos Harbour': 3, 'Commodore Channel': 3, 'Ebute Metta Creek': 2, 'Lighthouse Creek': 1, 'Badagry Creek': 3}

def build(roads, marks, waters=None, blds=None):
    tile = [[W0] * W for _ in range(H)]; seed = [[0] * W for _ in range(H)]; rank = [[0] * W for _ in range(H)]; name = {}
    coast, ways = [], []
    for e in roads['elements']:
        if e['type'] != 'way' or 'geometry' not in e: continue
        t = e.get('tags', {}); pts = [ij(p['lat'], p['lon']) for p in e['geometry']]
        if t.get('natural') == 'coastline': coast.append(pts); continue
        hw = t.get('highway', '')
        if not hw: continue
        ways.append((hw.replace('_link', ''), t, pts))
    # the land: every tile some street runs through (bridges and causeways over water left out), one tile round it
    for hw, t, pts in ways:
        if t.get('bridge') == 'yes' or t.get('man_made') == 'bridge': continue
        for i, j in cells(pts): seed[j][i] = 1
    for b in blds or []:  # (and every building stands on land)
        i, j = int(b[0]), int(b[1])
        if 0 <= i < W and 0 <= j < H: seed[j][i] = 1
    R = max(1, round(SC))  # (a street's land reaches about 100 m round it)
    import numpy as np
    S0 = np.array(seed, dtype=bool); A = S0.copy()
    for d in range(1, R + 1): A[:, d:] |= S0[:, :-d]; A[:, :-d] |= S0[:, d:]  # (a square round each seed: along the rows,
    D = A.copy()
    for d in range(1, R + 1): D[d:, :] |= A[:-d, :]; D[:-d, :] |= A[d:, :]  # then down the columns)
    for j, i in zip(*np.nonzero(D)): tile[j][i] = LAND
    # the beach: the Atlantic coastline, and everything south of it is sea
    for pts in coast:
        for i, j in cells(pts): tile[j][i] = SAND
    for i in range(W):  # the sea from the bottom edge up to the sand
        for j in range(H - 1, -1, -1):
            if tile[j][i] == SAND: break
            if j < H - 1 and tile[j][i] == LAND and seed[j][i]: break
            tile[j][i] = W0
    # small pockets of water inside the land (pools, yards between streets) are land
    seen = [[False] * W for _ in range(H)]
    for j in range(H):
        for i in range(W):
            if tile[j][i] != W0 or seen[j][i]: continue
            q, comp, edge = [(i, j)], [], False; seen[j][i] = True
            while q:
                x, y = q.pop(); comp.append((x, y)); edge |= x in (0, W - 1) or y in (0, H - 1)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < W and 0 <= ny < H and not seen[ny][nx] and tile[ny][nx] == W0: seen[ny][nx] = True; q.append((nx, ny))
            if not edge and len(comp) <= 8 * SC * SC:
                for x, y in comp: tile[y][x] = LAND
    # the creeks and the canal that cut the land, cut back in (too narrow for the street outline to leave open);
    # where a road crosses one it becomes a bridge below
    for e in (waters or {}).get('elements', []):
        t = e.get('tags', {}); wd = CUTS.get(t.get('name'))
        if e['type'] != 'way' or wd is None: continue
        for i, j in cells([ij(p['lat'], p['lon']) for p in e['geometry']]):
            for y in range(j - wd, j + wd + 1):
                for x in range(i - wd, i + wd + 1):
                    if 0 <= x < W and 0 <= y < H and tile[y][x] == LAND: tile[y][x] = W0
    # the mainland is not ours: land joined to the west edge, or to the north edge west of the Lekki-Ikoyi link, goes
    # (the bridges still run out to the edge of the map, as they would out of the game's world)
    seen = [[False] * W for _ in range(H)]; cut = int(ij(LAT1, 3.445)[0])
    for j in range(H):
        for i in range(W):
            if tile[j][i] not in (LAND, SAND) or seen[j][i]: continue
            q, comp, main = [(i, j)], [], False; seen[j][i] = True
            while q:
                x, y = q.pop(); comp.append((x, y)); main |= (x == 0 and y < H * 0.45) or (y == 0 and x < cut)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < W and 0 <= ny < H and not seen[ny][nx] and tile[ny][nx] in (LAND, SAND): seen[ny][nx] = True; q.append((nx, ny))
            if main:
                for x, y in comp: tile[y][x] = W0
    # the roads: tertiary and up, the bigger road's name winning a shared tile; over water, a bridge (the mainland's own streets left off)
    # (biggest first, so a minor street can see whether a bigger one already serves its strip of the city)
    for hw, t, pts in sorted(ways, key=lambda w: -(RANK.get(w[0], 0) or 0.5)):
        r = RANK.get(hw, 0)
        if not r and hw in ('residential', 'unclassified') and length(pts) * TILE >= (1000 if TILE >= 100 else 90): r = 1  # (the long side streets too (a kilometre and more), so the blocks are city blocks)
        if not r: continue
        isb = t.get('bridge') == 'yes'
        if isb and length(pts) < 1.5 and r < 3: continue  # (culverts and short decks over drains: just road)
        cs = cells(pts)
        if all(tile[j][i] == W0 for i, j in cs) and not isb: continue  # (a street wholly on the cut-away mainland)
        if r <= 1 and not isb:  # a minor street running within a tile of a bigger one most of its way is left as the block's inside
            near = sum(any(0 <= x < W and 0 <= y < H and tile[y][x] in (ROAD, BRIDGE) for x in (i - 1, i, i + 1) for y in (j - 1, j, j + 1)) for i, j in cs)
            if near > 0.5 * len(cs): continue
        for i, j in cs:
            if tile[j][i] == W0 and not isb and not any(0 <= x < W and 0 <= y < H and tile[y][x] in (LAND, ROAD, SAND) for x, y in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1))): continue  # (its mainland end)
            if isb and tile[j][i] != ROAD: tile[j][i] = BRIDGE  # (only OSM's own bridges are decks; a street along a creek keeps its bank)
            elif tile[j][i] != BRIDGE: tile[j][i] = ROAD
            if r >= rank[j][i]: rank[j][i] = r; name[f'{i},{j}'] = t.get('name') or t.get('ref') or ''
    # old Lagos's streets run closer than a tile apart: where four road tiles make a square, the least of them gives way
    # to a plot (never a bridge, never a main road), so the streets read as streets and the blocks have room
    for _ in range(4):
        changed = 0
        for j in range(H - 1):
            for i in range(W - 1):
                sq = [(i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)]
                if not all(tile[y][x] == ROAD for x, y in sq): continue
                x, y = min(sq, key=lambda c: (rank[c[1]][c[0]], -sum(tile[c[1] + dy][c[0] + dx] == ROAD for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= c[0] + dx < W and 0 <= c[1] + dy < H)))
                if rank[y][x] >= 3: continue
                tile[y][x] = LAND; rank[y][x] = 0; name.pop(f'{x},{y}', None); changed += 1
        if not changed: break
    # the landmarks we place the game's buildings by, where OSM has them
    out = []
    by = {}
    for e in marks['elements']:
        t = e.get('tags', {}); c = e.get('center', e); n = t.get('name')
        if n and 'lat' in c: by.setdefault(n, (c['lat'], c['lon']))
    for key, label, kind in LANDMARKS:
        if key not in by: print('missing landmark', key); continue
        x, y = ij(*by[key])
        if 0 <= x < W and 0 <= y < H: out.append({'id': kind, 'name': label, 'osm': key, 'i': int(x), 'j': int(y), 'lat': round(by[key][0], 5), 'lon': round(by[key][1], 5)})
    return tile, rank, name, out

LANDMARKS = [  # (OSM name, the game's label, the game's kind)
    ('Tafawa Balewa Square', 'Tafawa Balewa Square', 'field'), ('Lagos Central Mosque', 'Lagos Central Mosque', 'mosque'),
    ('Cathedral Church of Christ', 'Cathedral Church of Christ', 'cathedral'), ('Holy Cross Cathedral', 'Holy Cross Cathedral', 'church'),
    ('NECOM House', 'NECOM House', 'towers'), ('Lagos City Hall', 'Lagos City Hall', 'hall'), ('Freedom Park', 'Freedom Park', 'park'),
    ('MUSON Centre', 'MUSON Centre', 'hall'), ('Obalende Bus Terminus', 'Obalende Motor Park', 'park'), ('Marina/CMS', 'CMS Ferry Terminal', 'ferry'),
    ('Idumota', 'Idumota', 'market'), ('Balogun Street', 'Balogun Market', 'market'), ('National Theatre', 'National Theatre', 'theatre'),
    ('Federal Palace & Casino', 'Federal Palace Hotel', 'hotel'), ('Eko Hotel', 'Eko Hotel & Suites', 'hotel'), ('Mega Plaza', 'Mega Plaza', 'mall'),
    ('Ikoyi Club', 'Ikoyi Club', 'golf'), ('Falomo Shopping Mall', 'Falomo Shopping Centre', 'mall'), ('Five Cowries Terminal', 'Five Cowries Terminal', 'ferry'),
    ('Dolphin Estate', 'Dolphin Estate', 'houses'), ('Banana Island', 'Banana Island', 'houses'), ('Landmark Towers', 'Landmark Towers', 'towers'),
    ('Landmark Centre', 'Landmark Centre', 'hall'), ('Eko Atlantic', 'Eko Atlantic', 'reclaimed'), ('Palms Shopping Mall', 'The Palms', 'mall'),
    ('Lekki Central Mosque', 'Lekki Central Mosque', 'mosque'), ('Jakande Market', 'Jakande Market', 'market'), ('Chevron Nigeria Head Office', 'Chevron HQ', 'towers'),
    ('Ikota Shopping Complex', 'Ikota Shopping Complex', 'mall'), ('Ajah Market', 'Ajah Market', 'market'), ('Abraham Adesanya Estate', 'Abraham Adesanya Estate', 'houses'),
    ('Dangote Industries Head Office', 'Dangote HQ', 'towers'), ('New Oniru Market', 'Oniru Market', 'market'), ('Fiki Marina', 'Fiki Marina', 'marina'),
]

# ---- the game's places on their real sites, and the real districts
# each place: (lat, lon, how). 'land' stands on land and touches a street (minor streets inside it are built over);
# 'fill' may be sandfilled out into the water (the made-up places, on new land, the way Lagos really grows); 'road'
# sits over the road it serves, which stays; 'water' stands in open water (WYRD Tower on its rock)
SITES = {
    'Lagos Central Mosque': (6.4574, 3.3882, 'land'), 'Balogun Market': (6.4612, 3.3868, 'land'), 'Idumota': (6.4636, 3.3838, 'land'),
    'Iga Idunganran': (6.4598, 3.3897, 'land'), 'Tinubu Square': (6.4548, 3.3902, 'land'), 'Cathedral Church of Christ': (6.4509, 3.3902, 'land'),
    'Tafawa Balewa Square': (6.4483, 3.3985, 'land'), 'The Marina & NECOM House': (6.4462, 3.3972, 'land'), 'Freedom Park': (6.4489, 3.3966, 'land'),
    'General Hospital': (6.4505, 3.3935, 'land'), 'Marina Jetty': (6.4495, 3.3898, 'shore'), 'Ikoyi Club 1938': (6.4495, 3.4236, 'land'),
    'Ikoyi waterfront': (6.4560, 3.4410, 'land'), 'Banana Island': (6.4605, 3.4545, 'land'), 'Banana Island Marina': (6.4632, 3.4575, 'shore'),
    'Banana Island gate': (6.4565, 3.4505, 'land'), 'Falomo Shopping Centre': (6.4448, 3.4282, 'land'), 'Obalende Motor Park': (6.4496, 3.4074, 'land'),
    'Ikoyi homes': (6.4585, 3.4330, 'land'), 'Old Ikoyi': (6.4530, 3.4150, 'land'), 'Eko Hotel': (6.4266, 3.4303, 'land'),
    'Lagos Civic Centre': (6.4352, 3.4202, 'land'), 'Muri Okunola Park': (6.4325, 3.4250, 'land'), 'Federal Palace Hotel': (6.4308, 3.4073, 'land'),
    'Bar Beach': (6.4180, 3.4190, 'fill'), 'Kuramo Beach': (6.4205, 3.4360, 'fill'), 'WYRD Studio': (6.4140, 3.4230, 'land'),
    'WYRD Tower': (6.4500, 3.4420, 'water'), 'Eko Atlantic City': (6.4090, 3.4160, 'land'), 'Eko Pearl Towers': (6.4170, 3.4110, 'land'),
    'Lekki Toll Gate': (6.4330, 3.4520, 'road'), 'Nike Art Gallery': (6.4420, 3.4710, 'land'), 'Lekki Conservation Centre': (6.4415, 3.5360, 'land'),
    'Circle Mall': (6.4385, 3.5180, 'land'), 'Elegushi Beach': (6.4255, 3.4880, 'fill'), 'Landmark Beach': (6.4215, 3.4480, 'fill'),
    'Lekki Phase 1': (6.4465, 3.4720, 'land'), 'Lekki estates': (6.4450, 3.4950, 'land'), 'Ajah Market': (6.4681, 3.5642, 'land'),
    'Victoria Garden City': (6.4580, 3.5520, 'land'), 'Ilashe Beach': (6.4010, 3.3800, 'fill'), 'Ilashe beach houses': (6.4030, 3.3880, 'fill'),
    'Club Ozumba': (6.4340, 3.4225, 'land'), 'Club Lekki': (6.4300, 3.4700, 'land'), 'Quilox': (6.4383, 3.4316, 'land'),
    'Secrets Palace': (6.4305, 3.4250, 'land'), 'VEIN Lagos': (6.4410, 3.4600, 'land'), 'Island Casino': (6.4280, 3.4220, 'land'),
    # the made-up places, each on new land at the edge of the real city
    'Lekki Free Zone Refinery': (6.4770, 3.5800, 'fill'), 'Tank farm': (6.4790, 3.5940, 'fill'), 'Free Zone Line': (6.4710, 3.5850, 'fill'),
    'Blue Line': (6.4795, 3.4700, 'fill'), 'Lagos Island Airport': (6.4760, 3.5150, 'fill'), 'Atlantic Gardens': (6.4040, 3.4210, 'fill'),
    'Ocean Crest': (6.4040, 3.4310, 'fill'), 'Island Reserve Bank': (6.4525, 3.3960, 'land'), 'Polanco': (6.4770, 3.4950, 'fill'),
    'Lekki Luxury Cars': (6.4770, 3.5470, 'fill'), 'Marina Court': (6.4000, 3.4050, 'fill'), 'Harbour View': (6.4000, 3.4120, 'fill'),
    'Eko Home Store': (6.4395, 3.5150, 'land'), 'National Grid': (6.4560, 3.5900, 'fill'), 'Welcome to Lagos Island': (6.4650, 3.3930, 'fill'),
    'The Arena': (6.4245, 3.4280, 'land'), 'Ad Island': (6.4505, 3.4500, 'fill'), 'HQ Row': (6.4370, 3.5050, 'land'),
    "No Man's Land gate": (6.4600, 3.4880, 'fill'), "No Man's Land helipad": (6.4640, 3.4960, 'fill'), "No Man's Land beach": (6.4630, 3.4900, 'fill'), "No Man's Land": (6.4660, 3.4900, 'fill'),
}
DISTRICTS = [  # first match wins: (id, name, lon0, lat0, lon1, lat1, extra)
    ('hqrow', 'HQ Row', 3.501, 6.435, 3.506, 6.439, {'fill': 'hq'}),  # (an estate of its own, about 550 m by 450 m)
    ('atlantic', 'Eko Atlantic', 3.380, 6.395, 3.445, 6.419, {'fill': 'city', 'newTown': True}),
    ('banana', 'Banana Island', 3.445, 6.452, 3.462, 6.470, {}),
    ('lagos', 'Lagos Island', 3.370, 6.440, 3.4065, 6.480, {}),
    ('vi', 'Victoria Island', 3.400, 6.419, 3.452, 6.443, {}),
    ('ikoyi', 'Ikoyi', 3.4065, 6.440, 3.462, 6.480, {}),
    ('lekki', 'Lekki', 3.452, 6.395, 3.545, 6.480, {}),
    ('ajah', 'Ajah', 3.545, 6.395, 3.600, 6.480, {}),
]

# No Man's Land: a private island of its own, sandfilled out in the lagoon north of Lekki, one bridge to the shore.
# Its parts as they stood on the old board, round a road across the middle: the gate, the mansions, the beach, the helipad
NML = {'lat': 6.4720, 'lon': 3.4900, 'w': 9, 'h': 5, 'road': 2,
       'parts': {"No Man's Land gate": (0, 3), "No Man's Land": (2, 0), "No Man's Land beach": (4, 3), "No Man's Land helipad": (6, 0)}}
ISLANDS = {}  # id: [i0, j0, i1, j1], for the districts

def place_island(tile, rank, occ, out, places):
    ci, cj = ij(NML['lat'], NML['lon']); w, h = NML['w'], NML['h']; i1, j1 = int(ci - w / 2), int(cj - h / 2); best = None
    def open_water(i0, j0):  # (water all round it, two tiles of it, so it is an island)
        return all(0 <= i < W and 0 <= j < H and tile[j][i] == W0 and occ[j][i] is None for j in range(j0 - 2, j0 + h + 2) for i in range(i0 - 2, i0 + w + 2))
    for r in range(60):
        ring = [(i, j) for i in range(i1 - r, i1 + r + 1) for j in range(j1 - r, j1 + r + 1) if max(abs(i - i1), abs(j - j1)) == r and open_water(i, j)]
        if ring: best = min(ring, key=lambda c: math.hypot(c[0] + w / 2 - ci, c[1] + h / 2 - cj)); break
    if not best: print('NO SITE', "No Man's Land island"); return set()
    i0, j0 = best
    for j in range(j0, j0 + h):
        for i in range(i0, i0 + w):
            tile[j][i] = ROAD if j == j0 + NML['road'] else SAND if j > j0 + NML['road'] else LAND; rank[j][i] = 1 if tile[j][i] == ROAD else 0
            occ[j][i] = "No Man's Land"  # (nothing else is routed across the island: its own road makes its one bridge)
    sizes = {p['name']: (p['w'], p['h']) for p in places}
    for nm, (di, dj) in NML['parts'].items():
        if nm not in sizes: continue
        out[nm] = [i0 + di, j0 + dj]; pw, ph = sizes[nm]
        for j in range(j0 + dj, j0 + dj + ph):
            for i in range(i0 + di, i0 + di + pw): occ[j][i] = nm
    ISLANDS['nml'] = [i0, j0, i0 + w - 1, j0 + h - 1]
    return set(NML['parts'])

def place_all(tile, rank, places):
    occ = [[None] * W for _ in range(H)]; out = {}
    done = place_island(tile, rank, occ, out, places); places = [p for p in places if p['name'] not in done]
    def street(i, j): return 0 <= i < W and 0 <= j < H and tile[j][i] == ROAD
    def ok(i0, j0, w, h, how):
        if i0 < 0 or j0 < 0 or i0 + w > W or j0 + h > H: return False
        for j in range(j0, j0 + h):
            for i in range(i0, i0 + w):
                t = tile[j][i]
                if occ[j][i] is not None or t == BRIDGE: return False
                if how == 'water' and t != W0: return False
                if how == 'land' and (t == W0 or (t == ROAD and rank[j][i] >= 3)): return False
                if how in ('fill', 'shore') and t == ROAD and rank[j][i] >= 3: return False
                if how == 'shore' and t == W0: return False
        ring = [(i, j) for i in range(i0 - 1, i0 + w + 1) for j in (j0 - 1, j0 + h)] + [(i, j) for j in range(j0, j0 + h) for i in (i0 - 1, i0 + w)]
        if how == 'shore': return any(0 <= i < W and 0 <= j < H and tile[j][i] == W0 for i, j in ring) and any(0 <= i < W and 0 <= j < H and tile[j][i] in (LAND, ROAD, SAND) for i, j in ring)
        if how == 'road': return any(tile[j][i] == ROAD and rank[j][i] >= 3 for j in range(j0, j0 + h) for i in range(i0, i0 + w))
        if how == 'land':  # (a landmark on land fronts a street)
            return any(street(i, j) for i in range(i0, i0 + w) for j in (j0 - 1, j0 + h)) or any(street(i, j) for j in range(j0, j0 + h) for i in (i0 - 1, i0 + w))
        return True
    for p in sorted(places, key=lambda p: {'land': 0, 'road': 1, 'shore': 2, 'water': 2, 'fill': 3}[p['how']]):
        ci, cj = ij(p['lat'], p['lon']); w, h = p['w'], p['h']; i1, j1 = int(ci - w / 2), int(cj - h / 2); best = None
        for r in range(min(120, int(40 * max(1, SC / 1.5)))):  # rings out from the real spot, the nearest that fits
            ring = [(i, j) for i in range(i1 - r, i1 + r + 1) for j in range(j1 - r, j1 + r + 1) if max(abs(i - i1), abs(j - j1)) == r]
            ring = [c for c in ring if ok(c[0], c[1], w, h, p['how'])]
            if ring: best = min(ring, key=lambda c: math.hypot(c[0] + w / 2 - ci, c[1] + h / 2 - cj)); break
        if not best: print('NO SITE', p['name']); continue
        i0, j0 = best; out[p['name']] = [i0, j0]
        for j in range(j0, j0 + h):
            for i in range(i0, i0 + w):
                occ[j][i] = p['name']
                if p['how'] != 'road': tile[j][i] = SAND if p['kind'] in ('beach', 'huts') else LAND
    connect(tile, rank, occ)  # (the streets joined up first, so every place's road in leads somewhere)
    def roads_in():
        # every place you can't drive to gets a road in: the shortest way from its edge to a street, over the land (a road)
        # or the water (a causeway bridge), round the other places (WYRD Tower keeps its solitude)
        for p in places:
            if p['name'] not in out or p['kind'] == 'wyrdtower': continue
            i0, j0 = out[p['name']]; w, h = p['w'], p['h']
            ring = [(i, j) for i in range(i0 - 1, i0 + w + 1) for j in (j0 - 1, j0 + h)] + [(i, j) for j in range(j0, j0 + h) for i in (i0 - 1, i0 + w)]
            ring = [(i, j) for i, j in ring if 0 <= i < W and 0 <= j < H]
            if any(tile[j][i] == ROAD for i, j in ring): continue
            prev = {c: None for c in ring if occ[c[1]][c[0]] is None}; q = list(prev); hit = None
            for c in q:
                if tile[c[1]][c[0]] in (ROAD, BRIDGE) and c not in ring: hit = c; break
                for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (c[0] + d[0], c[1] + d[1])
                    if 0 <= n[0] < W and 0 <= n[1] < H and n not in prev and occ[n[1]][n[0]] is None: prev[n] = c; q.append(n)
            if not hit: print('NO ROAD IN', p['name']); continue
            c = prev[hit]
            while c is not None:
                i, j = c; tile[j][i] = BRIDGE if tile[j][i] == W0 else ROAD; rank[j][i] = max(rank[j][i], 1); c = prev[c]
    roads_in()
    connect(tile, rank, occ)
    tidy_ends(tile, rank, occ)
    roads_in()  # (again: tidying can take away the street a road in had led to)
    connect(tile, rank, occ)
    return out

def tidy_ends(tile, rank, occ):
    # a street that stops dead: carried on straight to the next street if one is a few tiles ahead over open land, else,
    # if it's only a short stub, taken up (a street to a place, a bridge, or one leaving the map stays)
    isr = lambda i, j: 0 <= i < W and 0 <= j < H and tile[j][i] in (ROAD, BRIDGE)
    nbs = lambda i, j: [(i + di, j + dj) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)) if isr(i + di, j + dj)]
    def keep(i, j):
        if i in (0, W - 1) or j in (0, H - 1) or tile[j][i] == BRIDGE: return True
        return any(0 <= i + di < W and 0 <= j + dj < H and occ[j + dj][i + di] is not None for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    for _ in range(3):
        for j in range(H):
            for i in range(W):
                if not isr(i, j) or len(nbs(i, j)) != 1 or keep(i, j): continue
                (ni, nj), = nbs(i, j); di, dj = i - ni, j - nj; path = []
                for k in range(1, 5):
                    x, y = i + di * k, j + dj * k
                    if not (0 <= x < W and 0 <= y < H) or occ[y][x] is not None or tile[y][x] == W0: path = None; break
                    if isr(x, y): break
                    path.append((x, y))
                else: path = None
                if path is not None:
                    for x, y in path: tile[y][x] = ROAD; rank[y][x] = max(rank[y][x], 1)
                    continue
                stub = [(i, j)]; c = (ni, nj)
                while len(stub) < 4 and len(nbs(*c)) == 2 and not keep(*c): stub.append(c); c = next(n for n in nbs(*c) if n not in stub)
                if len(stub) <= 3 and len(nbs(*c)) >= 3:
                    for x, y in stub: tile[y][x] = LAND; rank[y][x] = 0
    # last, any two streets that only touch at a corner get the corner paved, so they meet side to side
    for j in range(H - 1):
        for i in range(W):
            for di in (1, -1):
                x, y = i + di, j + 1
                if not (isr(i, j) and isr(x, y)) or isr(x, j) or isr(i, y): continue
                for cx, cy in ((x, j), (i, y)):
                    if 0 <= cx < W and occ[cy][cx] is None and tile[cy][cx] != W0: tile[cy][cx] = ROAD; rank[cy][cx] = max(rank[cy][cx], 1); break
                else:
                    cx, cy = (x, j) if occ[j][x] is None else (i, y)
                    if 0 <= cx < W and occ[cy][cx] is None: tile[cy][cx] = BRIDGE; rank[cy][cx] = max(rank[cy][cx], 1)

def connect(tile, rank, occ):
    # every street joined to the rest, so you can drive the whole of Lagos: each cut-off network (the minor streets that
    # link it in are below a tile's notice) gets the cheapest way to another, along land if it can (a street), over
    # water only where it must (a bridge: ten times the cost), never through a place; networks join up until one is left
    import heapq
    isr = lambda i, j: tile[j][i] in (ROAD, BRIDGE)
    comp = [[-1] * W for _ in range(H)]; members = []
    for j in range(H):
        for i in range(W):
            if not isr(i, j) or comp[j][i] >= 0: continue
            q = [(i, j)]; comp[j][i] = len(members)
            for x, y in q:
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < W and 0 <= ny < H and comp[ny][nx] < 0 and isr(nx, ny): comp[ny][nx] = len(members); q.append((nx, ny))
            members.append(q)
    if len(members) <= 1: return
    up = list(range(len(members)))
    def find(k):
        while up[k] != k: up[k] = up[up[k]]; k = up[k]
        return k
    main = max(range(len(members)), key=lambda k: len(members[k]))
    stub = {k for k, m in enumerate(members) if any(i in (0, W - 1) or j in (0, H - 1) for i, j in m) and 2 * sum(tile[j][i] == BRIDGE for i, j in m) >= len(m)}  # (a bridge stub out to the mainland: left as it is)
    cap = 150 * SC / 3
    for _ in range(6):
        changed = False
        for k in sorted(range(len(members)), key=lambda k: -len(members[k])):
            if find(k) == find(main) or k in stub or not members[k]: continue
            g = find(k); dist = {}; prev = {}; hp = []
            for i, j in members[k]: dist[(i, j)] = 0; prev[(i, j)] = None; heapq.heappush(hp, (0, i, j))
            hit = None
            while hp:
                d, i, j = heapq.heappop(hp)
                if d > dist.get((i, j), 1e9) or d > cap: continue
                if comp[j][i] >= 0 and find(comp[j][i]) != g: hit = (i, j); break
                for ni, nj in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                    if not (0 <= ni < W and 0 <= nj < H) or occ[nj][ni] is not None: continue
                    nd = d + (10 if tile[nj][ni] == W0 else 1)
                    if nd < dist.get((ni, nj), 1e9): dist[(ni, nj)] = nd; prev[(ni, nj)] = (i, j); heapq.heappush(hp, (nd, ni, nj))
            if not hit:  # (too far to be worth a road: the scrap of street is taken up)
                for i, j in members[k]: tile[j][i] = LAND if tile[j][i] == ROAD else W0; rank[j][i] = 0; comp[j][i] = -1
                members[k] = []; continue
            c = prev[hit]
            while c is not None and comp[c[1]][c[0]] < 0:
                i, j = c; tile[j][i] = BRIDGE if tile[j][i] == W0 else ROAD; rank[j][i] = max(rank[j][i], 1); comp[j][i] = k; members[k].append(c); c = prev[c]
            up[g] = find(comp[hit[1]][hit[0]]); changed = True
        if not changed: break

def game_places(html):
    import re
    s = html[html.index('const PLACES = ['):]; s = s[:s.index('\n  ];')]; out = []
    for m in re.finditer(r"\['([a-z]+)', (\d+), (\d+), (\d+), (\d+), (\"[^\"]*\"|'[^']*')", s):
        name = m.group(6)[1:-1]; key = next((k for k in sorted(SITES, key=len, reverse=True) if name.startswith(k)), None)
        if not key: print('no site for', name); continue
        lat, lon, how = SITES[key]
        out.append({'kind': m.group(1), 'name': name, 'w': int(m.group(4)), 'h': int(m.group(5)), 'lat': lat, 'lon': lon, 'how': how})
    return out

def districts():
    out = [{'id': 'nml', 'name': "No Man's Land", 'rect': ISLANDS['nml'], 'fill': 'palm'}] if 'nml' in ISLANDS else []
    for did, name, lo0, la0, lo1, la1, extra in DISTRICTS:
        a, b = ij(la1, lo0); c, d = ij(la0, lo1)
        out.append(dict({'id': did, 'name': name, 'rect': [max(0, int(a)), max(0, int(b)), min(W - 1, int(c)), min(H - 1, int(d))]}, **extra))
    return out

if __name__ == '__main__':
    roads = json.load(open(sys.argv[1], encoding='utf-8')); marks = json.load(open(sys.argv[2], encoding='utf-8'))
    waters = json.load(open(sys.argv[5], encoding='utf-8')) if len(sys.argv) > 5 else None
    tile, rank, name, lm = build(roads, marks, waters)
    html = open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[3])), '..', 'index.html'), encoding='utf-8').read()
    gp = game_places(html); sites = place_all(tile, rank, gp)
    for j in range(H):  # (a street the places built over leaves no rank behind)
        for i in range(W):
            if tile[j][i] not in (ROAD, BRIDGE): rank[j][i] = 0
    names = sorted(set(name.values()) - {''}); nid = {n: k + 1 for k, n in enumerate(names)}
    doc = {'attribution': '© OpenStreetMap contributors (ODbL)', 'w': W, 'h': H, 'tile_m': TILE, 'bbox': [LON0, LAT0, LON1, LAT1],
           'codes': {'water': W0, 'land': LAND, 'sand': SAND, 'road': ROAD, 'bridge': BRIDGE},
           'rows': [''.join(str(c) for c in row) for row in tile],
           'roadRank': [''.join(str(c) for c in row) for row in rank],
           'roadNames': names, 'roadAt': {k: nid[v] for k, v in name.items() if v}, 'landmarks': lm, 'places': sites, 'districts': districts()}
    json.dump(doc, open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    js = {k: doc[k] for k in ('attribution', 'w', 'h', 'tile_m', 'rows', 'places', 'districts')}
    open(sys.argv[3][:-5] + '.js', 'w', encoding='utf-8').write('// Lagos from OpenStreetMap, made by tools/osm2board.py. Map data (c) OpenStreetMap contributors, ODbL.\nwindow.LAGOS_BOARD = ' + json.dumps(js, ensure_ascii=False, separators=(',', ':')) + ';\n')
    c = collections.Counter(ch for r in doc['rows'] for ch in r)
    print(f'{W}x{H} tiles', dict(c), len(names), 'road names', len(lm), 'landmarks')
    if len(sys.argv) > 4:
        from PIL import Image, ImageDraw
        S = max(2, round(600 / W * 2.5)); im = Image.new('RGB', (W * S, H * S)); g = ImageDraw.Draw(im)
        pal = {W0: (70, 130, 190), LAND: (120, 165, 95), SAND: (230, 210, 150), ROAD: (60, 60, 60), BRIDGE: (220, 60, 200)}
        for j in range(H):
            for i in range(W):
                cc = pal[tile[j][i]]
                if tile[j][i] == ROAD and rank[j][i] >= 4: cc = (240, 140, 40)
                g.rectangle([i * S, j * S, i * S + S - 1, j * S + S - 1], fill=cc)
        for nm, (pi, pj) in sites.items():
            p = next(q for q in gp if q['name'] == nm); g.rectangle([pi * S, pj * S, (pi + p['w']) * S - 1, (pj + p['h']) * S - 1], outline=(255, 230, 0)); g.text((pi * S + 2, pj * S + 1), nm[:16], fill=(255, 255, 120))
        for m in []:
            x, y = m['i'] * S + S // 2, m['j'] * S + S // 2; g.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 255, 255), outline=(0, 0, 0)); g.text((x + 6, y - 6), m['name'], fill=(255, 255, 255))
        im.save(sys.argv[4])
