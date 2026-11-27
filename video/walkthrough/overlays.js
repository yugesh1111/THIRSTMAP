// Render the walkthrough GIFs' text overlays (title cards, captions, panels) in the site's own fonts.
// Usage: node video/walkthrough/overlays.js <spec.json> <out-dir>
// spec.json: {"name": "<html>", ...}; each becomes <out-dir>/ov_<name>.png, transparent, at 2x of a 960x540 canvas.
const { chromium } = require('../node_modules/playwright');
const fs = require('fs'), path = require('path');
const [specFile, out] = process.argv.slice(2);
const W = 960, H = 540;
const css = `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=block');
*{margin:0;box-sizing:border-box} body{background:transparent;font-family:Inter,sans-serif;color:#eef2f4}
.full{width:${W}px;height:${H}px;position:relative;overflow:hidden}
.kicker{font:500 13px 'JetBrains Mono',monospace;letter-spacing:.22em;color:#5aa7ff;text-transform:uppercase}
.big{font:800 60px/1.06 'Plus Jakarta Sans',sans-serif;letter-spacing:-.03em}
.mid{font:800 32px/1.12 'Plus Jakarta Sans',sans-serif;letter-spacing:-.02em}
.sub{font:400 19px/1.45 Inter;color:#a7b3ba}
.body{font:400 16.5px/1.5 Inter;color:#b9c4ca}
.body b{color:#fff;font-weight:600}
.grad{background:linear-gradient(92deg,#5aa7ff,#2fd0a5 55%,#f08a4b);-webkit-background-clip:text;color:transparent}
.cap{display:inline-flex;align-items:center;gap:12px;padding:11px 20px 11px 14px;border-radius:14px;
  background:rgba(14,19,22,.88);border:1px solid rgba(90,167,255,.35);box-shadow:0 10px 40px rgba(0,0,0,.55);
  font:500 18px/1.3 Inter;color:#eef2f4}
.n{font:700 13px 'JetBrains Mono';color:#0e1316;background:#5aa7ff;border-radius:7px;padding:4px 8px;white-space:nowrap}
.n.red{background:#ff7a7a} .n.green{background:#46d07a} .n.amber{background:#f0a54b}
b{color:#fff;font-weight:600} .r{color:#ff7a7a;font-weight:600} .g{color:#46d07a;font-weight:600} .a{color:#f0a54b;font-weight:600} .bl{color:#5aa7ff;font-weight:600}
.row{display:flex;gap:14px;margin-top:26px}
.pill{font:500 14px Inter;padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);color:#cfd8dd}
.url{font:500 15px 'JetBrains Mono';color:#5aa7ff}
.stat{flex:1;padding:18px 20px;border-radius:16px;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.1)}
.stat b{display:block;font:700 40px/1 'Plus Jakarta Sans';margin-bottom:8px} .stat span{font:400 14.5px/1.35 Inter;color:#a7b3ba}
.label{display:inline-block;font:600 13px Inter;padding:6px 11px;border-radius:9px;background:rgba(14,19,22,.85);border:1px solid rgba(255,255,255,.16);color:#eef2f4}
.stampbox{display:inline-flex;align-items:center;gap:10px;padding:10px 18px;border-radius:12px;font:700 22px 'Plus Jakarta Sans'}
.ok{background:rgba(20,80,45,.92);border:2px solid #46d07a;color:#c9f5d8} .bad{background:rgba(90,22,22,.92);border:2px solid #ff7a7a;color:#ffd6d6}
.mono{font-family:'JetBrains Mono',monospace}
`;
(async () => {
  const spec = JSON.parse(fs.readFileSync(specFile, 'utf8'));
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
  for (const [name, body] of Object.entries(spec)) {
    await page.setContent(`<style>${css}</style><div id="x" style="display:inline-block">${body}</div>`, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.locator('#x').screenshot({ path: path.join(out, `ov_${name}.png`), omitBackground: true });
  }
  await browser.close();
})();
