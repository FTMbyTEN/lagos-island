"""The island's buses: each runs between two real terminals (OpenStreetMap's bus stations, and named bus stops where a
route ends at one), along the real streets from end to end, stopping at the real bus stops it passes. OpenStreetMap has
no bus-route lines for Lagos Island, so a route's path is the drivable way between its two ends over the real road
network, keeping to the main roads as a bus does. Writes web/map/transit.json in world units.

  python tools/transit.py <overpass json of the bus stations>

The Overpass query (box 6.395,3.37,6.48,3.6): nwr[amenity=bus_station], nwr[public_transport=station]. Map data (c)
OpenStreetMap contributors, ODbL.
"""
import glob, heapq, json, math, os, sys
os.environ.setdefault('OSM_TILE', '15')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osm2world as W

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web', 'map')
# the routes: well-known Lagos Island bus and danfo routes, each between two real ends. (model: the yellow danfo, or
# the blue bus of the BRT and LAGBUS routes)
ROUTES = [
    ('CMS', 'Obalende', 'danfo'),
    ('Idumota', 'Obalende', 'danfo'),
    ('Obalende', 'Abraham Adesanya', 'danfo'),
    ('CMS', 'Chevron', 'danfo_b'),
    ('TBS', 'Falomo', 'danfo_b'),
    ('Obalende', 'Law School', 'danfo'),
    ('CMS', 'Ikate', 'danfo_b'),
]
# the ends, by the name they go by on the bus boards, and the real place each one is
ENDS = {'CMS': 'Marina/CMS Ferry Terminal', 'Obalende': 'Obalende Bus Terminus', 'TBS': 'Tafawa Balewa Square Bus Terminal'}
FACTOR = {0: 0.75, 1: 0.75, 2: 0.8, 3: 0.85, 4: 0.95, 5: 1.25, 6: 1.6}  # (a bus keeps to the big roads)


def deck_y(cum, cls, s):  # as deckY in the game
    L = cum[-1]; H = 6.5 if cls <= 3 else 1.2; R = 32 if cls <= 3 else 10
    return 0.5 + H * max(0, min(1, s / R, (L - s) / R))


def main():
    roads, seen = [], set()
    for f in glob.glob(os.path.join(ROOT, 'world', '*.json')):
        for r in json.load(open(f, encoding='utf-8'))['r']:
            if r[1] and r[0] > 3: continue  # (no footbridges)
            t = tuple(r)
            if t in seen or len(r) < 6: continue
            seen.add(t); roads.append((r[0], r[1], [(r[k], r[k + 1]) for k in range(2, len(r), 2)]))
    use = {}
    for _, _, pts in roads:
        for p in pts: use[p] = use.get(p, 0) + 1
    # the network: each road cut at every point it shares with another, so a bus can turn at every real junction
    adj = {}
    for cls, br, pts in roads:
        cum = [0.0]
        for a, b in zip(pts, pts[1:]): cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]) / 10)
        cut = [0] + [k for k in range(1, len(pts) - 1) if use[pts[k]] > 1] + [len(pts) - 1]
        for k0, k1 in zip(cut, cut[1:]):
            piece = list(range(k0, k1 + 1)); L = cum[k1] - cum[k0]
            if L <= 0: continue
            e = {'cls': cls, 'br': br, 'pts': pts, 'cum': cum, 'idx': piece, 'L': L}
            adj.setdefault(pts[k0], []).append((pts[k1], e, 1)); adj.setdefault(pts[k1], []).append((pts[k0], e, -1))
    nodes = list(adj)
    def near_node(x, z):
        return min(nodes, key=lambda p: (p[0] / 10 - x) ** 2 + (p[1] / 10 - z) ** 2 if any(e['cls'] <= 4 for _, e, _ in adj[p]) else 1e18)
    def route(a, b):
        g = {a: 0}; prev = {}; h = lambda p: math.hypot(p[0] - b[0], p[1] - b[1]) / 10 * 0.75; q = [(h(a), a)]
        while q:
            _, p = heapq.heappop(q)
            if p == b: break
            for n, e, d in adj[p]:
                c = g[p] + e['L'] * FACTOR[e['cls']]
                if c < g.get(n, 1e18): g[n] = c; prev[n] = (p, e, d); heapq.heappush(q, (c + h(n), n))
        if b not in prev: return None
        out = []; p = b
        while p != a: p0, e, d = prev[p]; out.append((e, d)); p = p0
        return out[::-1]
    # the ends: the bus stations, and the named stops
    ends = {}
    for e in json.load(open(sys.argv[1], encoding='utf-8'))['elements']:
        nm = e.get('tags', {}).get('name')
        if not nm: continue
        if e['type'] == 'node': lat, lon = e['lat'], e['lon']
        elif 'geometry' in e: lat = sum(g['lat'] for g in e['geometry']) / len(e['geometry']); lon = sum(g['lon'] for g in e['geometry']) / len(e['geometry'])
        else: continue
        ends[nm] = W.wu(lat, lon)
    feat = json.load(open(os.path.join(ROOT, 'features.json'), encoding='utf-8'))
    for x, z, nm in feat['stops']:
        if nm and nm not in ends: ends[nm] = (x, z)
    out = []
    for A, B, model in ROUTES:
        pa, pb = ends.get(ENDS.get(A, A)), ends.get(ENDS.get(B, B))
        if not pa or not pb: print('no end for', A, B); continue
        na, nb = near_node(*pa), near_node(*pb); path = route(na, nb)
        if not path: print('no way', A, B); continue
        P, Y, C = [], [], []  # the points, the height at each (up on a bridge's deck), the class of the road to the next
        def put(x, z, y, c):
            if P and abs(P[-2] - x) < 1e-6 and abs(P[-1] - z) < 1e-6: C[-1] = c; return
            P.extend([x, z]); Y.append(round(y, 2)); C.append(c)
        for e, d in path:
            idx = e['idx'] if d > 0 else e['idx'][::-1]; pts, cum = e['pts'], e['cum']
            for k0, k1 in zip(idx, idx[1:]):
                (ax, az), (bx, bz) = pts[k0], pts[k1]; ax, az, bx, bz = ax / 10, az / 10, bx / 10, bz / 10
                n = max(1, int(abs(cum[k1] - cum[k0]) // 8)) if e['br'] else 1  # (on a bridge, a point every 8 units, so the ramps come out right)
                for m in range(n):
                    u = m / n; s = cum[k0] + (cum[k1] - cum[k0]) * u
                    put(round(ax + (bx - ax) * u, 1), round(az + (bz - az) * u, 1), deck_y(cum, e['cls'], s) if e['br'] else 0.07, e['cls'])
                put(bx, bz, deck_y(cum, e['cls'], cum[k1]) if e['br'] else 0.07, e['cls'])
        # the real stops on the way: each by the road (within its width and a little), at its distance along
        cumR = [0.0]
        for k in range(2, len(P), 2): cumR.append(cumR[-1] + math.hypot(P[k] - P[k - 2], P[k + 1] - P[k - 1]))
        stops = []
        for x, z, nm in feat['stops']:
            best = None
            for k in range(0, len(P) - 2, 2):
                ax, az, bx, bz = P[k], P[k + 1], P[k + 2], P[k + 3]; dx, dz = bx - ax, bz - az; L2 = dx * dx + dz * dz or 1
                u = max(0, min(1, ((x - ax) * dx + (z - az) * dz) / L2)); dd = math.hypot(ax + dx * u - x, az + dz * u - z)
                if dd < 14 and (best is None or dd < best[0]): best = (dd, cumR[k // 2] + u * math.sqrt(L2))
            if best and 20 < best[1] < cumR[-1] - 20 and not any(abs(s - best[1]) < 40 for s, _ in stops): stops.append((round(best[1], 1), nm))
        stops.sort()
        out.append({'a': A, 'b': B, 'model': model, 'p': P, 'y': Y, 'c': C, 'stops': [[s, n] for s, n in stops], 'L': round(cumR[-1])})
        print(f'{A} - {B}: {round(cumR[-1] * 1.5 / 1000, 1)} km, {len(P) // 2} points, {len(stops)} stops')
    json.dump({'attribution': '© OpenStreetMap contributors (ODbL)', 'routes': out}, open(os.path.join(ROOT, 'transit.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__': main()
