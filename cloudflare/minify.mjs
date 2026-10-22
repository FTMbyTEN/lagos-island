// Writes web/index.min.html: the page with its scripts minified (terser) and its styles' whitespace squeezed, for phones
// on slow connections. The worker serves it at / ; web/index.html stays the readable source. Runs before each deploy.
import { readFileSync, writeFileSync } from 'node:fs';
import { minify } from 'terser';

const web = new URL('../web/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const src = readFileSync(web + 'index.html', 'utf8');
let out = '', at = 0;
const re = /<script(\s[^>]*)?>([\s\S]*?)<\/script>/g;
for (let m; (m = re.exec(src));) {
  const attrs = m[1] || '', body = m[2];
  out += src.slice(at, m.index);
  at = m.index + m[0].length;
  if (/type="importmap"/.test(attrs) || !body.trim()) { out += m[0]; continue; }
  const r = await minify(body, { module: /type="module"/.test(attrs), compress: { passes: 1 }, mangle: true, format: { comments: false } });
  if (!r.code) throw new Error('minify failed');
  out += `<script${attrs}>${r.code}</script>`;
}
out += src.slice(at);
// the styles: comments out, runs of whitespace squeezed
out = out.replace(/<style>([\s\S]*?)<\/style>/g, (_, css) => '<style>' + css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\s+/g, ' ').replace(/\s*([{};,>])\s*/g, '$1') + '</style>');
writeFileSync(web + 'index.min.html', out);
console.log(`index.min.html: ${(src.length / 1024).toFixed(0)} KB -> ${(out.length / 1024).toFixed(0)} KB`);
