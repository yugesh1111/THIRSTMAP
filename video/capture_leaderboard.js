// Screenshots of the leaderboard page for the films: serve docs/ first (python3 -m http.server 8765 -d docs).
//   node video/capture_leaderboard.js http://127.0.0.1:8765/leaderboard/
const { chromium } = require('playwright');
const path = require('path');
const OUT = path.join(__dirname, 'capture');
(async () => {
  const url = process.argv[2] || 'http://127.0.0.1:8765/leaderboard/';
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, colorScheme: 'light' });
  await p.goto(url);
  await p.waitForSelector('#board tr[data-id]');
  await p.evaluate(() => document.fonts.ready);
  const top = p.locator('.wrap');
  const box = await p.locator('.tablewrap').boundingBox(), head = await p.locator('h1').boundingBox();
  await p.screenshot({ path: path.join(OUT, 'lb_board.jpg'), type: 'jpeg', quality: 88,
    clip: { x: box.x - 8, y: head.y - 40, width: box.width + 16, height: box.y + box.height - head.y + 52 } });
  await p.click('#board tr:first-child');
  await p.waitForSelector('.card');
  const card = p.locator('.card');
  const cb = await card.boundingBox();
  await p.screenshot({ path: path.join(OUT, 'lb_card.jpg'), type: 'jpeg', quality: 88, fullPage: true,
    clip: { x: cb.x, y: cb.y, width: cb.width, height: Math.min(cb.height, 760) } });
  console.log('saved lb_board.jpg, lb_card.jpg');
  await b.close();
})();
