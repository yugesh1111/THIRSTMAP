// Capture the real demo, leaderboard and human-test pages (dark theme, 2x) for the README walkthrough GIFs.
// Usage: node video/walkthrough/capture.js <base-url> <out-dir>
//   <base-url> serves the repo root, e.g.  python -m http.server 8799 --directory .
// Only requests to <base-url> and Google Fonts are allowed: the human test's answer upload (Netlify) is blocked, so
// nothing is sent anywhere.
const { chromium } = require('../node_modules/playwright');
const fs = require('fs'), path = require('path');
const [base = 'http://127.0.0.1:8799', out = 'video/build/walkthrough'] = process.argv.slice(2);

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2, colorScheme: 'dark' });
  await ctx.route('**/*', r => {
    const u = r.request().url();
    return (u.startsWith(base) || /fonts\.(googleapis|gstatic)\.com/.test(u)) ? r.continue() : r.abort();
  });
  const page = await ctx.newPage();
  const meta = {};
  const settle = async () => { await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(500); };
  const shot = async (sel, name, parts = {}) => {
    const el = page.locator(sel).first();
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(350);
    const b = await el.boundingBox();
    await el.screenshot({ path: path.join(out, name + '.png') });
    const boxes = {};
    for (const [k, s] of Object.entries(parts)) {
      boxes[k] = await page.locator(s).evaluateAll((els, o) => els.map(e => {
        const r = e.getBoundingClientRect(); return [r.left - o.x, r.top - o.y, r.width, r.height];
      }), { x: b.x, y: b.y });
    }
    meta[name] = { w: b.width, h: b.height, boxes };
  };

  // demo: "What we found"
  await page.goto(base + '/docs/demo/index.html', { waitUntil: 'networkidle' });
  await settle();
  await shot('#found .wrap', 'found', { cards: '#found .find' });

  // leaderboard: table, report card, the three "score your own model" steps, then the sample file
  await page.goto(base + '/docs/leaderboard/index.html', { waitUntil: 'networkidle' });
  await page.waitForSelector('#board tr[data-id]');
  await settle();
  await shot('.tablewrap', 'board', { rows: '#board tr', heads: '.tablewrap thead th' });
  await page.locator('#board tr[data-id]').first().click();
  await page.waitForTimeout(800);
  await shot('#cardslot .card', 'card', { stats: '#cardslot .stat' });
  await shot('.steps', 'lb_steps', { steps: '.steps .step', sample: '#sample', drop: '#drop', pack: '.steps .step a.btn' });
  await page.locator('#sample').click();
  await page.waitForSelector('#board tr.yours');
  await page.waitForTimeout(1200);
  await shot('.tablewrap', 'lb_yours_board', { rows: '#board tr', yours: '#board tr.yours' });
  await shot('#cardslot .card', 'lb_yours_card', { stats: '#cardslot .stat' });

  // human test: intro + first question, tick an answer, next question
  await page.goto(base + '/human_eval/index.html', { waitUntil: 'networkidle' });
  await settle();
  await page.setViewportSize({ width: 1200, height: 940 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  const viewport = async name => {
    await page.screenshot({ path: path.join(out, name + '.png') });
    const boxes = {};
    for (const [k, s] of Object.entries({ opts: '#stage .opts label', next: '#next', count: '#count', img: '#stage img' })) {
      boxes[k] = await page.locator(s).evaluateAll(els => els.map(e => {
        const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height];
      }));
    }
    meta[name] = { w: 1200, h: 940, boxes };
  };
  await page.evaluate(() => window.scrollTo(0, 0));
  await viewport('human_1');
  await page.locator('#stage .opts label').nth(2).click();
  await page.waitForTimeout(300);
  await viewport('human_1_ticked');
  await page.locator('#next').click();
  await page.waitForTimeout(700);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await viewport('human_2');

  fs.writeFileSync(path.join(out, 'meta.json'), JSON.stringify(meta, null, 1));
  await browser.close();
})();
