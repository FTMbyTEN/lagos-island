import json, numpy as np, os
CT = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
def load(path):
    g = json.load(open(path)); d = os.path.dirname(path)
    bufs = [open(os.path.join(d, b['uri']), 'rb').read() for b in g['buffers']]
    def acc(i):
        a = g['accessors'][i]; bv = g['bufferViews'][a['bufferView']]; n = NC[a['type']]; dt = CT[a['componentType']]
        st = bv.get('byteStride'); off = bv.get('byteOffset', 0) + a.get('byteOffset', 0); b = bufs[bv['buffer']]
        if st and st != n * np.dtype(dt).itemsize:
            raw = np.frombuffer(b, np.uint8, a['count'] * st, off).reshape(a['count'], st)[:, :n * np.dtype(dt).itemsize].copy()
            return raw.view(dt).reshape(a['count'], n)
        return np.frombuffer(b, dt, a['count'] * n, off).reshape(a['count'], n).copy()
    return g, acc
def joints(path):
    g, acc = load(path); sk = g['skins'][0]; ibm = acc(sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
    names = [g['nodes'][j]['name'] for j in sk['joints']]; glob = np.linalg.inv(ibm)
    return g, acc, names, glob
