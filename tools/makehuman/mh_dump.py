import sys, os, json
import numpy as np
M = sys.argv[1]; OUT = sys.argv[2]; os.chdir(M)
sys.path[:0] = [M, M+'/lib', M+'/apps', M+'/shared', M+'/apps/gui', M+'/core']
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import makehuman; makehuman.set_sys_path(); makehuman.make_user_dir(); makehuman.get_platform_paths()
import files3d, human, humanmodifier, getpath, skeleton, proxy
from core import G
base = files3d.loadMesh(getpath.getSysDataPath('3dobjs/base.obj'), maxFaces=5)
h = human.Human(base); G.app = type('A', (), {'selectedHuman': h, 'progress': lambda *a, **k: None})()
humanmodifier.loadModifiers(getpath.getSysDataPath('modifiers/modeling_modifiers.json'), h)
SP = lambda p: getpath.getSysDataPath(p)
for g, spec in json.loads(sys.argv[3]).items():
    h.resetMeshValues()
    for k, v in spec["mods"].items(): getattr(h, "set" + k)(v)
    h.applyAllTargets()
    skel = skeleton.load(SP('rigs/default.mhskel'), h.meshData); skel.autoBuildWeightReferences(skel)
    raw = skel.getVertexWeights()
    out = {'bones': [], 'parent': [], 'head': [], 'tail': [], 'roll': []}
    for b in skel.getBones():
        out['bones'].append(b.name); out['parent'].append(b.parent.name if b.parent else '')
        out['head'].append(b.getRestHeadPos()); out['tail'].append(b.getRestTailPos()); out['mat'] = out.get('mat', []) + [b.matRestGlobal.tolist()]
    parts = {}
    for key, (path, typ) in spec['parts'].items():
        px = proxy.loadProxy(h, SP(path), type=typ)
        mesh, obj = px.loadMeshAndObject(h)
        co = px.getCoords()
        w = px.getVertexWeights(raw, skel)
        J = np.zeros((len(co), 4), int); W = np.zeros((len(co), 4))
        bi = {n: i for i, n in enumerate(out['bones'])}
        acc = [[] for _ in range(len(co))]
        for bn, (vs, ws) in w.data.items():
            for v, ww in zip(vs, ws): acc[v].append((ww, bi[bn]))
        for v, a in enumerate(acc):
            a.sort(reverse=True); a = a[:4]
            for k2, (ww, j) in enumerate(a): J[v, k2] = j; W[v, k2] = ww
        W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
        faces = mesh.fvert; uvi = mesh.fuvs; uv = mesh.texco
        tex = px.material.diffuseTexture if px.material else ''
        parts[key] = dict(co=co, J=J, W=W, faces=faces, uvi=uvi, uv=uv, tex=str(tex))
        print(g, key, co.shape, faces.shape, tex)
    np.savez(OUT + '/mh_' + g + '.npz', head=np.array(out['head']), tail=np.array(out['tail']), mat=np.array(out['mat']),
             bones=np.array(out['bones']), parent=np.array(out['parent']), **{k + '__' + a: v for k, d in parts.items() for a, v in d.items()})
