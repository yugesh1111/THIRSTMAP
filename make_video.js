// Record a ~75 s captioned walkthrough of the demo page (docs/demo/index.html) for the submission.
// Usage: node make_video.js [docs/demo/index.html] [docs/video]
//        -> docs/video/thirstmap_demo.webm, then make_video.sh encodes MP4 + GIF teaser with ffmpeg.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const page_url = 'file://' + path.resolve(process.argv[2] || 'docs/demo/index.html');
const out_dir = path.resolve(process.argv[3] || 'docs/video');
fs.mkdirSync(out_dir, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, colorScheme: 'light',
                                         recordVideo: { dir: out_dir, size: { width: 1280, height: 720 } } });
  const page = await ctx.newPage();
  await page.goto(page_url);
  await page.addStyleTag({ content: `#cap{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:99;
    max-width:1100px;background:rgba(15,34,48,.94);color:#f3f5f2;font:600 25px/1.35 system-ui,sans-serif;
    padding:14px 22px;border-radius:12px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,.25)}
    #cap small{display:block;font-weight:400;font-size:18px;color:#bfd0da;margin-top:4px}
    html{scroll-behavior:smooth}` });
  await page.evaluate(() => { const d = document.createElement('div'); d.id = 'cap'; document.body.appendChild(d); });
  const cap = (t, sub = '') => page.evaluate(([t, s]) => {
    document.getElementById('cap').innerHTML = t + (s ? `<small>${s}</small>` : ''); }, [t, sub]);
  const wait = (ms) => page.waitForTimeout(ms);
  const to = async (sel, offset = 70) => {
    await page.evaluate(([s, o]) => { const e = document.querySelector(s);
      if (e) window.scrollTo({ top: e.getBoundingClientRect().top + window.scrollY - o, behavior: 'smooth' }); }, [sel, offset]);
    await wait(1400);
  };
  const step = async (n) => to(`.steps .step:nth-child(${n})`, 40);

  await cap('ThirstMap: can AI trace water through the landscape?',
            'India’s data centres need water. AI tools are being asked where their wastewater goes.');
  await wait(5000);
  await to('h2');
  await cap('We tested open models and Gemini on the same questions',
            'Open models score at chance level. Gemini does far better, but look at the twins.');
  await wait(6500);

  await step(1); await cap('1 · The code builds the land', 'so it already knows every answer'); await wait(3800);
  await step(2); await cap('2 · It simulates where every drop of water flows', 'priority-flood + D8 routing'); await wait(3800);
  await step(3); await cap('3 · It places a data centre, its outfall, villages and traps', 'V6 is close, but on another stream'); await wait(4200);
  await step(4); await cap('4 · It traces the answer downhill', 'no model and no person involved'); await wait(3800);
  await step(5); await cap('5 · An independent library re-checks every answer', '99.7% of cells agree; same answer to 10 of 10 questions'); await wait(4200);
  await step(7); await cap('7 · The answer path is checked in the pixels the model sees', 'a question that fails a check is dropped, never edited'); await wait(4200);
  await step(8); await cap('8 · A twin moves one thing, so the answer must change', 'only a model that really looks gets both right'); await wait(4800);

  await to('#where', 20);
  await cap('Gemini gets the original right…', 'blue: the true water path · green: right · red: wrong'); await wait(4500);
  await page.evaluate(() => window.scrollBy({ top: 260, behavior: 'smooth' })); await wait(1200);
  await cap('…then gets the twin wrong', 'one thing changed and the correct answer changed; Gemini’s answer did not follow'); await wait(5500);

  await to('#tasks', 20);
  await page.selectOption('#fr', 'frontier'); await wait(800);
  await cap('Every question, every reply, scored automatically', 'Gemini and open models · same images, same prompts'); await wait(3500);
  await to('#list article', 90);
  const bo = await page.$('#list article .bo');
  if (bo) { await bo.click(); await cap('Where Gemini sent the water', 'drawn on the exact image it saw'); await wait(4200); }
  const bk = await page.$('#list article .bk');
  if (bk) { await bk.click(); await cap('The answer key from the simulation', 'red: where the wastewater really goes'); await wait(4200); }

  await to('h2');
  await cap('No model, Gemini included, got both halves of a before-and-after pair right',
            'Live demo, code and 5,761 tasks: github.com/yugesh1111/THIRSTMAP');
  await wait(6000);

  const video = page.video();
  await ctx.close();
  await browser.close();
  const src = await video.path();
  fs.renameSync(src, path.join(out_dir, 'thirstmap_demo.webm'));
  console.log('recorded', path.join(out_dir, 'thirstmap_demo.webm'));
})();
