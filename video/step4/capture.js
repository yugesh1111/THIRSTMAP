// Capture the real demo and leaderboard pages (dark theme, 2x) for the README step 4 GIF.
// Usage: node video/step4/capture.js <base-url> <out-dir>     (base-url serves docs/, e.g. python -m http.server --directory docs)
const { chromium } = require('../node_modules/playwright');
const fs = require('fs'), path = require('path');
const [base = 'http://127.0.0.1:8799', out = 'video/build/step4'] = process.argv.slice(2);
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2, colorScheme: 'dark' });
  const page = await ctx.newPage();
  const meta = {};
  const shot = async (sel, name, parts = {}) => {
    const el = page.locator(sel).first();
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
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
  await page.goto(base + '/demo/index.html', { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await shot('#found .wrap', 'found', { cards: '#found .find' });
  await page.goto(base + '/leaderboard/index.html', { waitUntil: 'networkidle' });
  await page.waitForSelector('#board tr[data-id]');
  await page.evaluate(() => document.fonts.ready);
  await shot('.tablewrap', 'board', { rows: '#board tr', heads: '.tablewrap thead th' });
  await page.locator('#board tr[data-id]').first().click();
  await page.waitForTimeout(800);
  await shot('#cardslot .card', 'card', { stats: '#cardslot .stat' });
  fs.writeFileSync(path.join(out, 'meta.json'), JSON.stringify(meta, null, 1));
  await browser.close();
})();
