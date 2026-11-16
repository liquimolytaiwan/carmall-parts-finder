// Shared Playwright routing: real origins, local files.
const fs = require('fs'), path = require('path');
const HOME = process.env.HOME;
const REPOS = { 'carmall-parts-finder': HOME + '/projects/carmall-parts-finder',
                'carmall-wiper-finder': HOME + '/projects/carmall-wiper-finder',
                'carmall-ngk-finder': HOME + '/projects/carmall-ngk-finder' };
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css',
                '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
const H = __dirname;
function page(snippetFile, extra) {
  const snip = fs.readFileSync(path.isAbsolute(snippetFile) ? snippetFile : path.join(H, snippetFile), 'utf8');
  return '<!doctype html><html><head><meta charset="utf-8"><title>store</title></head><body>' +
    '<a id="top-link" href="#top">top</a><div style="height:200px">store header</div>' + snip + (extra || '') +
    '<div style="height:1200px">footer</div></body></html>';
}
async function setup(ctx, pages) {
  await ctx.route('https://liquimolytaiwan.github.io/**', r => {
    const u = new URL(r.request().url());
    const parts = u.pathname.split('/').filter(Boolean);
    const root = REPOS[parts[0]];
    if (!root) return r.fulfill({ status: 404, body: 'nf' });
    let fp = path.join(root, ...parts.slice(1));
    if (u.pathname.endsWith('/')) fp = path.join(fp, 'index.html');
    if (!fs.existsSync(fp) || fs.statSync(fp).isDirectory()) return r.fulfill({ status: 404, body: 'nf' });
    r.fulfill({ status: 200, contentType: TYPES[path.extname(fp)] || 'application/octet-stream', body: fs.readFileSync(fp) });
  });
  await ctx.route('https://www.carmall.com.tw/**', r => {
    const u = new URL(r.request().url());
    const p = pages[u.pathname];
    if (p) return r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: p });
    r.fulfill({ status: 404, body: 'nf' });
  });
  await ctx.route('https://evil.example/**', r => r.fulfill({ status: 200, contentType: 'text/html',
    body: '<script>parent.postMessage({type:"carmallFinderState",finder:"wiper",state:"b=EVIL"},"*");' +
          'parent.postMessage({type:"carmallFinderHeight",height:4999},"*");</script>' }));
  // everything else (fonts, analytics) blocked
  await ctx.route(/^(?!https:\/\/(liquimolytaiwan\.github\.io|www\.carmall\.com\.tw|evil\.example)\/).*/, r => r.abort());
}
module.exports = { setup, page };
