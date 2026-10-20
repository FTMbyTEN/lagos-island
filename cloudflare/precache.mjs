// Lists everything the game needs (the page and every model, texture and icon in web/) into web/precache.json, for the
// service worker's "Install app" download. Runs before each deploy (npm run deploy).
import { readdirSync, statSync, writeFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const web = new URL('../web/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const keep = /\.(html|glb|gltf|bin|jpg|jpeg|png|webp|webmanifest)$/i;
const out = ['./'];
const walk = (d) => { for (const n of readdirSync(d)) { const p = join(d, n); if (statSync(p).isDirectory()) walk(p); else if (keep.test(n) && n !== 'index.html') out.push(relative(web, p).split(sep).join('/')); } };
walk(web);
// three.js and its loaders, from the CDN the page imports them from
out.push('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js', 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/GLTFLoader.js', 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/utils/SkeletonUtils.js', 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/libs/meshopt_decoder.module.js', 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/utils/BufferGeometryUtils.js');
writeFileSync(join(web, 'precache.json'), JSON.stringify(out));
console.log(`precache.json: ${out.length} files`);
// the build's version: the page checks it to tell players when an update is out
writeFileSync(join(web, 'version.json'), JSON.stringify({ v: new Date().toISOString() }));
