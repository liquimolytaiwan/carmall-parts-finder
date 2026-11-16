const { chromium } = require(process.env.HOME + '/.npm/_npx/705bc6b22212b352/node_modules/playwright-core');
const { setup } = require('./serve.js');
const BASES = { wiper: 'https://liquimolytaiwan.github.io/carmall-wiper-finder/',
  plugs: 'https://liquimolytaiwan.github.io/carmall-ngk-finder/',
  filters: 'https://liquimolytaiwan.github.io/carmall-parts-finder/filters/',
  pads: 'https://liquimolytaiwan.github.io/carmall-parts-finder/pads/',
  tires: 'https://liquimolytaiwan.github.io/carmall-parts-finder/tires/' };
(async () => {
  const b = await chromium.launch({ executablePath: process.env.PW_EXE });
  const ctx = await b.newContext();
  await setup(ctx, {});
  let total = 0, bad = 0;
  for (const [key, base] of Object.entries(BASES)) {
    const p = await ctx.newPage();
    await p.goto(base);
    await p.waitForFunction(() => document.querySelector('.cl-share') && document.querySelectorAll('#sel-brand option').length > 1);
    const rows = await p.evaluate(() => {
      const B = document.getElementById('sel-brand'), M = document.getElementById('sel-model'),
            Y = document.getElementById('sel-year'), R = document.getElementById('result');
      const fire = (s, v) => { s.value = v; s.dispatchEvent(new Event('change')); };
      const out = [];
      for (const bv of [...B.options].map(o => o.value).filter(Boolean)) {
        fire(B, bv);
        for (const mv of [...M.options].map(o => o.value).filter(Boolean)) {
          fire(B, bv); fire(M, mv);
          if (!R.hidden && R.innerHTML) { out.push([location.hash, R.innerHTML]); continue; }
          for (const yv of (Y ? [...Y.options].map(o => o.value).filter(Boolean) : [])) {
            fire(Y, yv); if (!R.hidden && R.innerHTML) out.push([location.hash, R.innerHTML]);
          }
        }
      }
      return out;
    });
    await p.close();
    const hashes = new Set(rows.map(r => r[0]));
    console.log(`${key}: ${rows.length} results, ${hashes.size} distinct links`);
    if (hashes.size !== rows.length) { console.log('  DUPLICATE LINKS'); bad++; }
    // reopen each link in a fresh load, 8 at a time
    const pages = await Promise.all([...Array(8)].map(() => ctx.newPage()));
    let i = 0, kbad = 0;
    await Promise.all(pages.map(async pg => {
      while (i < rows.length) {
        const n = i++; const [hash, html] = rows[n];
        await pg.goto(base + '?rt=' + n + hash);
        try {
          await pg.waitForFunction(() => { const r = document.getElementById('result'); return r && !r.hidden && r.innerHTML.length > 50; }, null, { timeout: 6000 });
          const got = await pg.$eval('#result', r => r.innerHTML);
          if (got !== html) { kbad++; if (kbad < 5) console.log('  MISMATCH', decodeURIComponent(hash)); }
        } catch (e) { kbad++; if (kbad < 5) console.log('  NO RESULT', decodeURIComponent(hash)); }
      }
    }));
    await Promise.all(pages.map(pg => pg.close()));
    console.log(`  reopened ${rows.length}, failures ${kbad}`);
    total += rows.length; bad += kbad;
  }
  console.log(bad ? `\nFAILURES ${bad} / ${total}` : `\nALL ${total} LINKS ROUND-TRIP`);
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
