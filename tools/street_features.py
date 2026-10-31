"""The real street furniture from OpenStreetMap, so the game puts things where they are and nowhere else: traffic
signals, pedestrian crossings, bus stops (with their names) and kiosks. Writes web/map/features.json in world units.

  python tools/street_features.py <overpass json>

The Overpass query (nodes in the map's box 6.395,3.37,6.48,3.6): highway=traffic_signals|bus_stop|crossing|street_lamp,
traffic_sign=*, information=guidepost, advertising=*, shop=kiosk, public_transport=platform. Map data (c) OpenStreetMap
contributors, ODbL.
"""
import json, os, sys
os.environ.setdefault('OSM_TILE', '15')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osm2world as W

def main():
    els = json.load(open(sys.argv[1], encoding='utf-8'))['elements']
    out = {'attribution': '© OpenStreetMap contributors (ODbL)', 'signals': [], 'crossings': [], 'stops': [], 'kiosks': [], 'lamps': [], 'signs': []}
    for e in els:
        if e['type'] != 'node': continue
        t = e.get('tags', {}); x, z = W.wu(e['lat'], e['lon']); p = [round(x, 1), round(z, 1)]
        h = t.get('highway')
        if h == 'traffic_signals': out['signals'].append(p)
        elif h == 'crossing': out['crossings'].append(p + [t.get('crossing', '')])
        elif h == 'bus_stop' or t.get('public_transport') == 'platform': out['stops'].append(p + [t.get('name', '')])
        elif h == 'street_lamp': out['lamps'].append(p)
        elif t.get('shop') == 'kiosk': out['kiosks'].append(p)
        elif 'traffic_sign' in t or t.get('information') == 'guidepost': out['signs'].append(p + [t.get('destination', t.get('name', ''))])
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web', 'map', 'features.json')
    json.dump(out, open(f, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print({k: len(v) for k, v in out.items() if isinstance(v, list)})

if __name__ == '__main__': main()
