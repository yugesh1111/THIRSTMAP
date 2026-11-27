// Render the title card, end card and captions of the step 4 GIF in the site's own fonts (transparent PNGs, 2x).
// Usage: node video/step4/overlays.js <out-dir>
const { chromium } = require('../node_modules/playwright');
const fs = require('fs'), path = require('path');
const out = process.argv[2] || 'video/build/step4';
const W = 960, H = 540;
const css = `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&family=Space+Grotesk:wght@500;700&display=block');
*{margin:0;box-sizing:border-box} body{background:transparent;font-family:Inter,sans-serif;color:#eef2f4}
.full{width:${W}px;height:${H}px;position:relative;overflow:hidden}
.kicker{font:500 13px 'JetBrains Mono',monospace;letter-spacing:.22em;color:#5aa7ff;text-transform:uppercase}
.big{font:700 64px/1.02 'Space Grotesk',sans-serif;letter-spacing:-.02em}
.sub{font:400 19px/1.45 Inter;color:#a7b3ba}
.grad{background:linear-gradient(92deg,#5aa7ff,#2fd0a5 55%,#f08a4b);-webkit-background-clip:text;color:transparent}
.cap{display:inline-flex;align-items:center;gap:12px;padding:11px 20px 11px 14px;border-radius:14px;
  background:rgba(14,19,22,.86);border:1px solid rgba(90,167,255,.35);box-shadow:0 10px 40px rgba(0,0,0,.55);
  font:500 18px/1.3 Inter;color:#eef2f4;backdrop-filter:blur(6px)}
.cap .n{font:700 13px 'JetBrains Mono';color:#0e1316;background:#5aa7ff;border-radius:7px;padding:4px 8px}
.cap b{color:#fff;font-weight:600} .cap .r{color:#ff7a7a;font-weight:600} .cap .g{color:#46d07a;font-weight:600}
.row{display:flex;gap:14px;margin-top:26px}
.pill{font:500 14px Inter;padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);color:#cfd8dd}
.url{font:500 15px 'JetBrains Mono';color:#5aa7ff}
.stat{flex:1;padding:18px 20px;border-radius:16px;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.1)}
.stat b{display:block;font:700 40px/1 'Space Grotesk';margin-bottom:8px} .stat span{font:400 14.5px/1.35 Inter;color:#a7b3ba}
`;
const pages = {
  title: `<div class="full" style="padding:150px 80px 0">
    <div class="kicker">ThirstMap · step 4 of 7</div>
    <div class="big" style="margin-top:18px">Test the <span class="grad">models</span></div>
    <div class="sub" style="margin-top:18px;max-width:640px">Frontier and open vision models answer the same water-flow questions. Every reply is scored against the answer key the code already knows.</div>
    <div class="row"><span class="pill">5 models</span><span class="pill">150 questions</span><span class="pill">19 before-and-after pairs</span><span class="pill">scored automatically</span></div></div>`,
  end: `<div class="full" style="padding:118px 72px 0">
    <div class="kicker">What the tests say</div>
    <div class="big" style="font-size:46px;margin-top:16px">The best model sees the water.<br><span class="grad">It still answers from habit.</span></div>
    <div class="row" style="margin-top:34px">
      <div class="stat"><b class="grad">77%</b><span>Gemini 3.5 Flash on 83 shared questions (guessing: 14%)</span></div>
      <div class="stat"><b>48% → 15%</b><span>Flash-Lite with the image, then without it</span></div>
      <div class="stat"><b style="color:#ff7a7a">6 of 19</b><span>pairs right on both halves, best model</span></div></div>
    <div style="margin-top:30px" class="url">yugesh1111.github.io/THIRSTMAP/leaderboard</div></div>`,
  cap1: `<div class="cap"><span class="n">77%</span><span>Gemini 3.5 Flash, the best model. <b>Guessing scores 14%.</b></span></div>`,
  cap2: `<div class="cap"><span class="n">IMAGE OFF</span><span>Hide the picture and Flash-Lite falls to <span class="r">chance</span>: the questions need it.</span></div>`,
  cap3: `<div class="cap"><span class="n">TWINS</span><span>One small change flips the answer. Best model: <span class="r">6 of 19</span> pairs.</span></div>`,
  cap4: `<div class="cap"><span class="n">LIVE</span><span>The leaderboard scores every reply <b>in your browser</b>, 150 questions.</span></div>`,
  cap5: `<div class="cap"><span class="n">PAIRS</span><span>Open models: <span class="r">0 of 19</span> pairs. Gemini gets most single questions, few pairs.</span></div>`,
  cap6: `<div class="cap"><span class="n">REPORT CARD</span><span>Click a model: skills, <span class="g">every pair</span>, <span class="r">every mistake</span>.</span></div>`,
};
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
  for (const [name, body] of Object.entries(pages)) {
    await page.setContent(`<style>${css}</style><div id="x" style="display:inline-block">${body}</div>`, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.locator('#x').screenshot({ path: path.join(out, `ov_${name}.png`), omitBackground: true });
  }
  await browser.close();
})();
