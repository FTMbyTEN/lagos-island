# Fit a MakeHuman body (exported by mh_dump.py) onto a Quaternius body's skeleton and bind pose, and write a glTF
# that keeps the Quaternius nodes, skin and joints (so every clip, outfit, hair and accessory still fits)
import sys, json, os, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qload import joints
QPATH, NPZ, OUT, NAME, SKIN = sys.argv[1:6]
g, acc, qn, qglob = joints(QPATH)
QJ = {n: qglob[i][:3, 3].astype(float) for i, n in enumerate(qn)}
qi = {n: i for i, n in enumerate(qn)}
qbody = max(g['meshes'], key=lambda m: acc(m['primitives'][0]['attributes']['POSITION']).shape[0])
qp = qbody['primitives'][0]
QV = acc(qp['attributes']['POSITION']).astype(float)
QJn = acc(qp['attributes']['JOINTS_0']).astype(int)
QW = acc(qp['attributes']['WEIGHTS_0']).astype(float)
if QW.max() > 1.5: QW /= 255.0
d = np.load(NPZ)
P = {k: d[k] for k in d.files}
mb = [str(x) for x in P['bones']]
MH = {n: P['head'][i].astype(float) for i, n in enumerate(mb)}
MT = {n: P['tail'][i].astype(float) for i, n in enumerate(mb)}

def qof(n):  # which Quaternius bone a MakeHuman bone's weight goes to
    side = {'.L': '_l', '.R': '_r'}.get(n[-2:], '')
    b = n[:-2] if side else n
    if b in ('root', 'spine05', 'pelvis'): return 'pelvis'
    if b == 'spine04': return 'spine_01'
    if b == 'spine03': return 'spine_02'
    if b in ('spine02', 'spine01', 'breast'): return 'spine_03'
    if b in ('clavicle', 'shoulder01'): return 'clavicle' + side
    if b.startswith('neck'): return 'neck_01'
    if b.startswith('upperarm'): return 'upperarm' + side
    if b.startswith('lowerarm'): return 'lowerarm' + side
    if b == 'wrist' or b.startswith('metacarpal'): return 'hand' + side
    if b.startswith('finger'):
        f, k = b[6:].split('-')
        return ['thumb', 'index', 'middle', 'ring', 'pinky'][int(f) - 1] + '_0' + k + side
    if b.startswith('upperleg'): return 'thigh' + side
    if b.startswith('lowerleg'): return 'calf' + side
    if b == 'foot': return 'foot' + side
    if b.startswith('toe'): return 'ball' + side
    return 'Head'
MAP = [qi[qof(n)] for n in mb]
s0 = np.ptp(QV[:, 1]) / np.ptp(P['body__co'][:, 1])

def seg(qa, qb, ma, mb2):  # takes the MakeHuman segment ma->mb2 onto the Quaternius one qa->qb
    um = mb2 - ma; Lm = np.linalg.norm(um); um = um / Lm
    uq = qb - qa; Lq = np.linalg.norm(uq); uq = uq / Lq
    v = np.cross(um, uq); c = float(um @ uq)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    R = np.eye(3) + K + K @ K / (1 + c)
    S = s0 * np.eye(3) + (Lq / Lm - s0) * np.outer(um, um)
    A = R @ S
    return A, qa - A @ ma

T = {}
torso = seg(QJ['pelvis'], QJ['neck_01'], MH['root'], MH['neck01'])
T['neck_01'] = seg(QJ['neck_01'], QJ['Head'], MH['neck01'], MH['head'])
for sd, S2 in (('_l', '.L'), ('_r', '.R')):
    T['upperarm' + sd] = seg(QJ['upperarm' + sd], QJ['lowerarm' + sd], MH['upperarm01' + S2], MH['lowerarm01' + S2])
    T['lowerarm' + sd] = seg(QJ['lowerarm' + sd], QJ['hand' + sd], MH['lowerarm01' + S2], MH['wrist' + S2])
    T['hand' + sd] = seg(QJ['hand' + sd], QJ['middle_01' + sd], MH['wrist' + S2], MH['finger3-1' + S2])
    for f, nm in enumerate(['thumb', 'index', 'middle', 'ring', 'pinky'], 1):
        for k in (1, 2, 3):
            qa = QJ['%s_0%d%s' % (nm, k, sd)]
            qb = QJ['%s_0%d%s' % (nm, k + 1, sd)] if k < 3 else QJ['%s_04_leaf%s' % (nm, sd)]
            ma = MH['finger%d-%d%s' % (f, k, S2)]
            mb2 = MH['finger%d-%d%s' % (f, k + 1, S2)] if k < 3 else MT['finger%d-%d%s' % (f, k, S2)]
            T['%s_0%d%s' % (nm, k, sd)] = seg(qa, qb, ma, mb2)
    T['thigh' + sd] = seg(QJ['thigh' + sd], QJ['calf' + sd], MH['upperleg01' + S2], MH['lowerleg01' + S2])
    T['calf' + sd] = seg(QJ['calf' + sd], QJ['foot' + sd], MH['lowerleg01' + S2], MH['foot' + S2])
    T['foot' + sd] = seg(QJ['foot' + sd], QJ['ball' + sd], MH['foot' + S2], MH['toe3-1' + S2])
    T['ball' + sd] = seg(QJ['ball' + sd], QJ['ball_leaf' + sd], MH['toe3-1' + S2], MT['toe3-3' + S2])

def qweights(J, W):  # MakeHuman joints/weights -> weights over the Quaternius joints
    out = np.zeros((len(J), len(qn)))
    for k in range(4): np.add.at(out, (np.arange(len(J)), [MAP[j] for j in J[:, k]]), W[:, k])
    return out
BW = qweights(P['body__J'], P['body__W'])
# the head: matched box to box to the Quaternius head, so its hair and hats still sit right
mhh = P['body__co'][BW[:, qi['Head']] > 0.6]
qhw = sum(QW[:, k] * (QJn[:, k] == qi['Head']) for k in range(4))
qh = QV[qhw > 0.6]
sc = np.ptp(qh, 0) / np.ptp(mhh, 0); sc[0] = sc[2] = (sc[0] + sc[2]) / 2
A = np.diag(sc); qc = (qh.max(0) + qh.min(0)) / 2; mc = (mhh.max(0) + mhh.min(0)) / 2
T['Head'] = (A, qc - A @ mc)
for b in qn: T.setdefault(b, T['Head'] if 'Head' in b else torso)
TA = np.stack([T[b][0] for b in qn]); Tt = np.stack([T[b][1] for b in qn])
def place(co, Wq): return np.einsum('nj,njk->nk', Wq, np.einsum('jab,nb->nja', TA, co) + Tt[None])

# ---- the glTF
bin_ = bytearray(); views = []; accs = []
def add(arr, typ, ct, target=None, mm=False):
    arr = np.ascontiguousarray(arr); off = len(bin_); bin_.extend(arr.tobytes()); bin_.extend(b'\0' * ((-len(bin_)) % 4))
    v = {'buffer': 0, 'byteOffset': off, 'byteLength': arr.nbytes}
    if target: v['target'] = target
    views.append(v)
    a = {'bufferView': len(views) - 1, 'componentType': ct, 'count': len(arr), 'type': typ}
    if mm: a.update(min=arr.min(0).tolist(), max=arr.max(0).tolist())
    accs.append(a); return len(accs) - 1
def prim(key, mat, Wq=None):
    co = P[key + '__co'].astype(float)
    if Wq is None: Wq = np.zeros((len(co), len(qn))); Wq[:, qi['Head']] = 1  # (eyes, brows and lashes ride the head)
    pos = place(co, Wq); fv = P[key + '__faces']; fu = P[key + '__uvi']; uv = P[key + '__uv']
    tris = []
    for f, u in zip(fv, fu):
        tris.append((f[0], f[1], f[2], u[0], u[1], u[2]))
        if f[3] != f[2]: tris.append((f[0], f[2], f[3], u[0], u[2], u[3]))
    tris = np.array(tris)
    pairs = np.stack([tris[:, :3].ravel(), tris[:, 3:].ravel()], 1)
    uniq, inv = np.unique(pairs, axis=0, return_inverse=True)
    vi, ui = uniq[:, 0], uniq[:, 1]; idx = inv.reshape(-1, 3).astype(np.uint32)
    n = np.zeros_like(pos); t = tris[:, :3]
    fn = np.cross(pos[t[:, 1]] - pos[t[:, 0]], pos[t[:, 2]] - pos[t[:, 0]])
    for k in range(3): np.add.at(n, t[:, k], fn)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    top = np.argsort(-Wq, 1)[:, :4]; tw = np.take_along_axis(Wq, top, 1); tw /= np.maximum(tw.sum(1, keepdims=True), 1e-9)
    at = {'POSITION': add(pos[vi].astype(np.float32), 'VEC3', 5126, 34962, True),
          'NORMAL': add(n[vi].astype(np.float32), 'VEC3', 5126, 34962),
          'TEXCOORD_0': add(np.stack([uv[ui, 0], 1 - uv[ui, 1]], 1).astype(np.float32), 'VEC2', 5126, 34962),
          'JOINTS_0': add(top[vi].astype(np.uint16), 'VEC4', 5123, 34962),
          'WEIGHTS_0': add(tw[vi].astype(np.float32), 'VEC4', 5126, 34962)}
    return {'attributes': at, 'indices': add(idx.ravel(), 'SCALAR', 5125, 34963), 'material': mat}
imgs = []; mats = []
def tex(src, out, size, fmt):
    im = Image.open(src).convert('RGBA' if fmt == 'PNG' else 'RGB'); im.thumbnail((size, size), Image.LANCZOS)
    im.save(os.path.join(OUT, out), fmt, **({'quality': 86} if fmt == 'JPEG' else {'optimize': True}))
    imgs.append({'uri': out}); return len(imgs) - 1
def mat(name, img, alpha=None, rough=0.6):
    m = {'name': name, 'pbrMetallicRoughness': {'baseColorTexture': {'index': img}, 'metallicFactor': 0, 'roughnessFactor': rough}}
    if alpha: m.update(alphaMode='MASK', alphaCutoff=alpha, doubleSided=True)
    mats.append(m); return len(mats) - 1
def underwear(src, out):  # paints plain dark underwear onto the skin texture (boxers; briefs and a bra), found by where each texel sits on the body
    im = Image.open(src).convert('RGB'); im.thumbnail((1024, 1024), Image.LANCZOS); a = np.asarray(im).astype(float); Hh, Ww = a.shape[:2]
    pos = place(P['body__co'].astype(float), BW); y0 = pos[:, 1].min(); H = np.ptp(pos[:, 1])
    h = (pos[:, 1] - y0) / H; ax = np.abs(pos[:, 0]) / H
    lo, hi = (0.415, 0.535) if NAME == 'm' else (0.455, 0.535)
    def cover(hv, axv): return ((hv > lo) & (hv < hi) & (axv < 0.12)) | ((NAME == 'f') & (hv > 0.695) & (hv < 0.748) & (axv < 0.105))
    uv = P['body__uv']; mask = np.zeros((Hh, Ww), bool)
    for f, u in zip(P['body__faces'], P['body__uvi']):
        for tri, tu in (((f[0], f[1], f[2]), (u[0], u[1], u[2])), ((f[0], f[2], f[3]), (u[0], u[2], u[3]))):
            if tri[1] == tri[2]: continue
            hv = h[list(tri)]; av = ax[list(tri)]
            if not cover(hv, av).any(): continue
            px = uv[list(tu)] * [Ww, Hh]; px[:, 1] = Hh - px[:, 1]
            x0, y0b = np.floor(px.min(0)).astype(int); x1, y1 = np.ceil(px.max(0)).astype(int)
            xs, ys = np.meshgrid(np.arange(max(0, x0), min(Ww, x1 + 1)), np.arange(max(0, y0b), min(Hh, y1 + 1)))
            if not xs.size: continue
            p = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], 1); A2 = np.array([px[1] - px[0], px[2] - px[0]]).T
            if abs(np.linalg.det(A2)) < 1e-9: continue
            l = np.linalg.solve(A2, (p - px[0]).T).T; b0 = 1 - l.sum(1); ok = (l[:, 0] >= -0.02) & (l[:, 1] >= -0.02) & (b0 >= -0.02)
            w = np.stack([b0, l[:, 0], l[:, 1]], 1)[ok]; hp = w @ hv; ap = w @ av; c = cover(hp, ap)
            mask[ys.ravel()[ok][c], xs.ravel()[ok][c]] = True
    shade = a.mean(2, keepdims=True) / 255.0
    a[mask] = (np.array([30, 30, 36]) * (0.75 + 0.5 * shade[mask]))
    Image.fromarray(a.clip(0, 255).astype(np.uint8)).save(os.path.join(OUT, out), 'JPEG', quality=86); imgs.append({'uri': out}); return len(imgs) - 1
mBody = mat('MI_Skin', underwear(SKIN, 'mh_skin_' + NAME + '.jpg'), rough=0.62)
mEye = mat('MI_Eyes', tex(str(P['eyes__tex']), 'mh_eye.png', 256, 'PNG'), rough=0.2)
mBrow = mat('MI_Brows', tex(str(P['brows__tex']), 'mh_brows_' + NAME + '.png', 256, 'PNG'), 0.35, 0.9)
mLash = mat('MI_Lashes', tex(str(P['lashes__tex']), 'mh_lashes_' + NAME + '.png', 256, 'PNG'), 0.35, 0.9)
meshes = [{'name': 'MH_Body', 'primitives': [prim('body', mBody, BW)]},
          {'name': 'MH_Eyes', 'primitives': [prim('eyes', mEye)]},
          {'name': 'MH_Brows', 'primitives': [prim('brows', mBrow), prim('lashes', mLash)]}]
nodes = json.loads(json.dumps(g['nodes']))
for nd in nodes:
    if 'mesh' in nd:
        old = g['meshes'][nd['mesh']]['name']
        nd['mesh'] = 0 if old == qbody['name'] else (1 if nd.get('name') == 'Eyes' else 2)
ibm = acc(g['skins'][0]['inverseBindMatrices']).astype(np.float32)
skin = dict(g['skins'][0]); skin['inverseBindMatrices'] = add(ibm, 'MAT4', 5126)
out = {'asset': {'version': '2.0', 'generator': 'Lagos Island MakeHuman fit', 'copyright': 'MakeHuman assets (CC0) on the Quaternius skeleton (CC0)'},
       'scene': 0, 'scenes': g['scenes'], 'nodes': nodes, 'meshes': meshes, 'skins': [skin], 'materials': mats,
       'textures': [{'source': i} for i in range(len(imgs))], 'images': imgs, 'accessors': accs, 'bufferViews': views,
       'buffers': [{'uri': 'mh_body_' + NAME + '.bin', 'byteLength': len(bin_)}]}
open(os.path.join(OUT, 'mh_body_' + NAME + '.bin'), 'wb').write(bin_)
json.dump(out, open(os.path.join(OUT, 'mh_body_' + NAME + '.gltf'), 'w'))
bp = place(P['body__co'].astype(float), BW)
print(NAME, 'ok height', bp[:, 1].min().round(3), bp[:, 1].max().round(3), 'Q', QV[:, 1].min().round(3), QV[:, 1].max().round(3), 'width', np.ptp(bp[:, 0]).round(3), np.ptp(QV[:, 0]).round(3), 'bytes', len(bin_))
