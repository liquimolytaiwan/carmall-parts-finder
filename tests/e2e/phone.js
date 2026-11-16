const { chromium } = require(process.env.HOME + '/.npm/_npx/705bc6b22212b352/node_modules/playwright-core');
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const URL0 = 'https://www.carmall.com.tw/pages/partsfinder#f=wiper&b=TOYOTA&m=COROLLA+ALTIS&y=%E7%AC%AC%E4%BA%8C%E4%BB%A3+%2808-13%29';
const ready = f => f.waitForFunction(() => { const r = document.getElementById('result'); return r && !r.hidden && r.innerHTML.length > 50 && !document.querySelector('.cl-share').hidden; }, null, { timeout: 20000 });
async function run(b, name, opts, stub) {
  const ctx = await b.newContext(Object.assign({ viewport: { width: 390, height: 844 } }, opts));
  // carmall only: lets the test read the clipboard back. The github.io frame gets NO grant — like a customer.
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'https://www.carmall.com.tw' });
  await ctx.route(/(googletagmanager|facebook\.(com|net)|doubleclick)/, r => r.abort());
  if (stub) await ctx.addInitScript(stub);
  const p = await ctx.newPage();
  const ga = []; p.on('request', r => { const u = r.url(); if (/google-analytics\.com\/g\/collect|analytics\.google\.com\/g\/collect/.test(u)) { const m = u.match(/[?&]en=([^&]+)/); ga.push(m ? m[1] : '?'); } });
  await p.goto(URL0, { waitUntil: 'load' });
  const f = await (await p.$('#cmf-frame')).contentFrame();
  await ready(f);
  const h0 = await p.$eval('#cmf-frame', e => e.getBoundingClientRect().height);
  await f.click('.cl-btn'); await p.waitForTimeout(800);
  const res = {
    msg: await f.$eval('.cl-msg', e => e.textContent),
    box: await f.$eval('.cl-url', e => e.hidden ? null : e.value),
    shared: await f.evaluate(() => window.__shared || null),
    clip: await p.evaluate(() => navigator.clipboard.readText().catch(() => 'readfail')),
    grew: (await p.$eval('#cmf-frame', e => e.getBoundingClientRect().height)) - h0,
    ga };
  await ctx.close();
  return res;
}
const shareStub = mode => `(() => { if (location.host !== 'liquimolytaiwan.github.io') return;
  navigator.share = function (d) { window.__shared = d;
    ${mode === 'ok' ? 'return Promise.resolve();' : `var e = new Error('x'); e.name = '${mode}'; return Promise.reject(e);`} }; })();`;
const clipFail = `(() => { if (location.host !== 'liquimolytaiwan.github.io') return;
  navigator.clipboard.writeText = function () { return Promise.reject(new Error('denied')); }; })();`;
(async () => {
  const b = await chromium.launch({ executablePath: process.env.PW_EXE });
  const phone = { hasTouch: true, isMobile: true };
  const want = 'https://www.carmall.com.tw/pages/partsfinder#f=wiper&b=TOYOTA&m=COROLLA+ALTIS&y=';
  let r = await run(b, 'desktop no grant', {}, null);
  ok(r.clip.startsWith(want) && /已複製/.test(r.msg), 'desktop, frame has no clipboard grant -> copied: ' + r.msg);
  ok(!r.ga.some((e, i) => e === 'page_view' && i > 0) && r.ga.filter(e => e === 'page_view').length <= 6, 'GA events during load+pick+share: ' + r.ga.join(','));
  r = await run(b, 'phone share ok', phone, shareStub('ok'));
  ok(r.shared && r.shared.url.startsWith(want), 'phone: share sheet gets store link: ' + (r.shared && r.shared.url.slice(0, 70)));
  ok(r.shared && /雨刷快速查詢｜TOYOTA COROLLA ALTIS/.test(r.shared.title), 'phone: share title ' + (r.shared && r.shared.title));
  r = await run(b, 'phone abort', phone, shareStub('AbortError'));
  ok(r.msg === '' && r.box === null, 'phone: customer closes sheet -> nothing happens');
  r = await run(b, 'phone notallowed', phone, shareStub('NotAllowedError'));
  ok(/已複製/.test(r.msg) && r.clip.startsWith(want), 'phone: share blocked -> falls back to copy: ' + r.msg);
  r = await run(b, 'desktop clip fails', {}, clipFail);
  ok(r.box && r.box.startsWith(want) && /請複製/.test(r.msg), 'copy blocked -> link box shown: ' + (r.box || '').slice(0, 60));
  ok(r.grew > 20, 'frame grew to show the box: +' + Math.round(r.grew) + 'px');
  console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
