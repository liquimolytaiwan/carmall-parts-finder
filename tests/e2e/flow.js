const { chromium } = require(process.env.HOME + '/.npm/_npx/705bc6b22212b352/node_modules/playwright-core');
const { setup, page: mk } = require('./serve.js');
const fs = require('fs');
const P = process.env.HOME + '/projects/';
const H = __dirname;
const PAGES = {
  '/pages/partsfinder': mk(P + 'carmall-parts-finder/embed-snippet.html'),
  '/pages/wiperguide': mk(P + 'carmall-wiper-finder/embed-snippet.html'),
  '/pages/plugsfinder': mk(P + 'carmall-ngk-finder/embed-snippet.html'),
  '/pages/wiperguide-old': mk('old-wiper-snippet.html'),
  '/pages/evil': mk(P + 'carmall-parts-finder/embed-snippet.html', '<iframe src="https://evil.example/x"></iframe>'),
};
let fails = 0;
function ok(c, m) { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; }
const S = 'https://www.carmall.com.tw/pages/';
(async () => {
  const b = await chromium.launch({ executablePath: process.env.PW_EXE });
  const ctx = await b.newContext({ viewport: { width: 420, height: 900 } });
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'https://www.carmall.com.tw' });
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'https://liquimolytaiwan.github.io' });
  await setup(ctx, PAGES);
  const p = await ctx.newPage();
  const dialogs = []; p.on('dialog', d => { dialogs.push(d.message()); d.dismiss(); });
  const frameEl = () => p.$('#cmf-frame');
  const fr = async () => (await frameEl()).contentFrame();
  const resultReady = async (f) => f.waitForFunction(() => { const r = document.getElementById('result'); return r && !r.hidden && r.innerHTML.length > 50; }, null, { timeout: 8000 });

  // 1. hub -> wiper -> pick -> hash -> share -> reopen -> back
  await p.goto(S + 'partsfinder');
  let f = await fr(); await f.waitForSelector('a.hub-card');
  await f.click('a.hub-card[href*="wiper"]');
  await p.waitForTimeout(500); f = await fr();
  await f.waitForFunction(() => document.querySelectorAll('#sel-brand option').length > 1);
  await f.selectOption('#sel-brand', 'TOYOTA'); await f.selectOption('#sel-model', 'COROLLA ALTIS');
  await f.selectOption('#sel-year', { label: '第二代 (08-13)' });
  await resultReady(f);
  await p.waitForTimeout(300);
  const h1 = new URL(p.url()).hash;
  ok(decodeURIComponent(h1.replace(/\+/g, ' ')) === '#f=wiper&b=TOYOTA&m=COROLLA ALTIS&y=第二代 (08-13)', 'parent hash mirrors pick: ' + decodeURIComponent(h1));
  const before = await f.$eval('#result', r => r.innerHTML);
  const vis = await f.$eval('.cl-share', e => !e.hidden).catch(() => false);
  ok(vis, 'share bar visible under new snippet');
  await f.click('.cl-btn');
  await p.waitForTimeout(500);
  const clip = await p.evaluate(() => navigator.clipboard.readText());
  ok(clip === S + 'partsfinder' + h1, 'clipboard = store link: ' + clip);
  const msgTxt = await f.$eval('.cl-msg', e => e.textContent);
  ok(/已複製/.test(msgTxt), 'copied message shown: ' + msgTxt);
  // reopen in fresh page
  const p2 = await ctx.newPage();
  await p2.goto(clip);
  const f2 = await (await p2.$('#cmf-frame')).contentFrame();
  await resultReady(f2);
  const after = await f2.$eval('#result', r => r.innerHTML);
  ok(after === before, 'shared link shows identical result');
  ok(await f2.$eval('#back-hub', e => !e.hidden), 'back link shown when opened via hub page');
  ok((await f2.url()).startsWith('https://liquimolytaiwan.github.io/carmall-wiper-finder/?from=hub#'), 'frame src: ' + (await f2.url()));
  // back to hub clears hash
  await f2.click('#back-hub'); await p2.waitForTimeout(800);
  ok(new URL(p2.url()).hash === '', 'back to hub clears store hash: "' + new URL(p2.url()).hash + '"');
  // change brand -> partial hash, share hidden
  await f.selectOption('#sel-brand', 'HONDA'); await p.waitForTimeout(200);
  ok(decodeURIComponent(new URL(p.url()).hash) === '#f=wiper&b=HONDA', 'partial pick hash: ' + new URL(p.url()).hash);
  ok(await f.$eval('.cl-share', e => e.hidden), 'share hidden without result');

  // 2. one deep link per finder through hub page
  const cases = [
    ['plugs', { b: 'KAWASAKI', m: null }], ['filters', {}], ['pads', {}], ['tires', {}]];
  for (const [key] of cases) {
    const pg = await ctx.newPage();
    await pg.goto(S + 'partsfinder#f=' + key);
    let ff = await (await pg.$('#cmf-frame')).contentFrame();
    await ff.waitForFunction(() => document.querySelectorAll('#sel-brand option').length > 1);
    // pick first brand, first model, and first year if asked
    const bv = await ff.$eval('#sel-brand', s => s.options[1].value); await ff.selectOption('#sel-brand', bv);
    const mv = await ff.$eval('#sel-model', s => s.options[1].value); await ff.selectOption('#sel-model', mv);
    const needYear = await ff.$eval('#sel-year', s => s.options.length > 1 && !(s.closest('[hidden]'))).catch(() => false);
    if (needYear) { const yv = await ff.$eval('#sel-year', s => s.options[1].value); await ff.selectOption('#sel-year', yv); }
    await resultReady(ff); await pg.waitForTimeout(200);
    const url = pg.url(), html = await ff.$eval('#result', r => r.innerHTML);
    const pg2 = await ctx.newPage(); await pg2.goto(url);
    const f3 = await (await pg2.$('#cmf-frame')).contentFrame(); await resultReady(f3);
    ok(await f3.$eval('#result', r => r.innerHTML) === html, key + ' deep link round trip: ' + decodeURIComponent(new URL(url).hash));
    await pg.close(); await pg2.close();
  }

  // 3. hostile links
  const hostile = ['#f=//evil.com', '#f=../x', '#f=WIPER', '#f=javascript:alert(1)', '#f=wiper&b=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E',
                   '#f=wiper&b=' + 'A'.repeat(200), '#f=wiper&b=TOYOTA&m=NOPE', '#f=constructor', '#f=__proto__'];
  for (const hh of hostile) {
    const pg = await ctx.newPage(); pg.on('dialog', d => { dialogs.push(d.message()); d.dismiss(); });
    await pg.goto(S + 'partsfinder' + hh); await pg.waitForTimeout(700);
    const src = await pg.$eval('#cmf-frame', e => e.src);
    ok(src.startsWith('https://liquimolytaiwan.github.io/carmall-'), 'hostile ' + hh.slice(0, 40) + ' -> ' + src.slice(0, 90));
    await pg.close();
  }
  // proto keys on single-finder page
  // 4. foreign frame messages ignored
  const pe = await ctx.newPage(); await pe.goto(S + 'evil'); await pe.waitForTimeout(1200);
  ok(new URL(pe.url()).hash === '', 'foreign frame cannot rewrite hash: ' + new URL(pe.url()).hash);
  const hgt = await pe.$eval('#cmf-frame', e => e.style.height);
  ok(hgt !== '4999px', 'foreign frame cannot resize: ' + hgt);
  // 5. hashchange: #top ignored, #f=tires reopens
  await pe.click('#top-link'); await pe.waitForTimeout(500);
  ok((await pe.$eval('#cmf-frame', e => e.src)).endsWith('/carmall-parts-finder/'), 'anchor #top leaves frame alone');
  await pe.evaluate(() => { location.hash = '#f=tires'; }); await pe.waitForTimeout(800);
  ok((await pe.$eval('#cmf-frame', e => e.src)).includes('/carmall-parts-finder/tires/'), 'hash link #f=tires reopens frame');
  // 6. single-finder pages
  const pw = await ctx.newPage(); await pw.goto(S + 'wiperguide#f=wiper&b=HONDA&m=CIVIC&y=' + encodeURIComponent('第九代 (12-17)'));
  const fw = await (await pw.$('#cmf-frame')).contentFrame(); await resultReady(fw);
  ok(await fw.$eval('#back-hub', e => e.hidden), 'wiperguide: no back link');
  ok((await fw.$$eval('#result .opt', e => e.length)) === 3, 'wiperguide deep link -> 3 option cards');
  await pw.goto('about:blank'); await pw.goto(S + 'wiperguide#f=plugs&b=HONDA'); await pw.waitForTimeout(500);
  ok((await pw.$eval('#cmf-frame', e => e.src)) === 'https://liquimolytaiwan.github.io/carmall-wiper-finder/', 'wiperguide ignores f=plugs');
  const pp = await ctx.newPage(); await pp.goto(S + 'plugsfinder#f=plugs&b=KAWASAKI&m=' + encodeURIComponent('ZX-6R 636cc'));
  const fp = await (await pp.$('#cmf-frame')).contentFrame();
  await fp.waitForFunction(() => document.querySelectorAll('#sel-model option').length > 1);
  await pp.waitForTimeout(300);
  const mlabel = await fp.$eval('#sel-model', s => s.options[s.selectedIndex].textContent);
  ok(/ZX-6R/.test(mlabel) && /636/.test(mlabel), 'plugs: cc-qualified model restored: ' + mlabel);
  // 6b. same finder, new link pasted in the same tab -> frame must switch car
  const ps = await ctx.newPage();
  await ps.goto(S + 'partsfinder#f=wiper&b=TOYOTA&m=' + encodeURIComponent('COROLLA ALTIS') + '&y=' + encodeURIComponent('第二代 (08-13)'));
  let fs1 = await (await ps.$('#cmf-frame')).contentFrame(); await resultReady(fs1);
  await ps.evaluate(() => { location.hash = '#f=wiper&b=HONDA&m=CIVIC&y=' + encodeURIComponent('第九代 (12-17)'); });
  await ps.waitForTimeout(800);
  fs1 = await (await ps.$('#cmf-frame')).contentFrame(); await resultReady(fs1);
  const veh = await fs1.$eval('.rc-veh', e => e.textContent);
  ok(/CIVIC/.test(veh) && /第九代/.test(veh), 'same-tab link switch shows new car: ' + veh.trim());
  ok(decodeURIComponent(new URL(ps.url()).hash).includes('CIVIC'), 'store hash after switch: ' + decodeURIComponent(new URL(ps.url()).hash));
  ok((await fs1.$$eval('#result .opt', e => e.length)) === 3, 'switched result has 3 cards');
  // 6c. unrelated anchor on the store page is not stripped when the hub loads
  const pa = await ctx.newPage(); await pa.goto(S + 'partsfinder#reviews'); await pa.waitForTimeout(800);
  ok(new URL(pa.url()).hash === '#reviews', 'unrelated #reviews kept: ' + new URL(pa.url()).hash);
  // 7. old snippet + new finder: height still works, no share button
  const po = await ctx.newPage(); await po.goto(S + 'wiperguide-old');
  const fo = await (await po.$('#cmw-frame')).contentFrame();
  await fo.waitForFunction(() => document.querySelectorAll('#sel-brand option').length > 1);
  await fo.selectOption('#sel-brand', 'TOYOTA'); await fo.selectOption('#sel-model', 'COROLLA ALTIS');
  await fo.selectOption('#sel-year', { label: '第二代 (08-13)' }); await resultReady(fo); await po.waitForTimeout(400);
  const oh = await po.$eval('#cmw-frame', e => parseInt(e.style.height || '0'));
  ok(oh > 400, 'old snippet still resizes: ' + oh);
  ok(await fo.$eval('.cl-share', e => e.hidden), 'old snippet: share hidden');
  ok(new URL(po.url()).hash === '', 'old snippet: store url untouched');
  ok(dialogs.length === 0, 'no dialogs fired: ' + dialogs.join('|'));
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
