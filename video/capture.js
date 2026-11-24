// Screenshots of the real demo page, the human test and the executed notebook, for the films (video/capture/).
// First: jupyter nbconvert --to html ThirstMap_quickstart.ipynb --output-dir video/capture --output notebook
const { chromium } = require('playwright');
const path = require('path');
const OUT = path.join(__dirname, 'capture');
const J = { type: 'jpeg', quality: 88 };
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2, colorScheme: 'light' });
  await p.goto('file:///home/user/thirstmap/docs/demo/index.html');
  await p.waitForTimeout(800);
  const shot = async (loc, name) => { await loc.scrollIntoViewIfNeeded(); await p.waitForTimeout(250); await loc.screenshot({ path: path.join(OUT, name), ...J }); console.log('saved', name); };

  // results tables (open models + frontier)
  const fr = p.locator('h3', { hasText: 'Frontier check' }).first();
  await shot(fr.locator('xpath=following-sibling::div[1]'), 'demo_frontier_table.jpg');

  // task browser: frontier filter, first card, then the answer key revealed
  await p.selectOption('#fr', 'frontier'); await p.waitForTimeout(500);
  const card = p.locator('#list article').first();
  await shot(card, 'demo_task.jpg');
  const bk = card.locator('.bk'); if (await bk.count()) { await bk.click(); await p.waitForTimeout(400); await shot(card, 'demo_task_key.jpg'); }
  const bo = card.locator('.bo'); if (await bo.count()) { await bo.click(); await p.waitForTimeout(400); await shot(card, 'demo_task_overlay.jpg'); }

  // try it yourself: answer the first question and check it
  const t = p.locator('#trylist article').first();
  const num = t.locator('input[type=number]'), radio = t.locator('input[type=radio]'), box = t.locator('input[type=checkbox]');
  if (await num.count()) await num.fill('2200'); else if (await radio.count()) await radio.first().check(); else await box.first().check();
  await t.locator('.chk').click(); await p.waitForTimeout(400);
  await shot(t, 'demo_try.jpg');

  // the human test page, first question
  const h = await b.newPage({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
  await h.goto('file:///home/user/thirstmap/human_eval/index.html'); await h.waitForTimeout(600);
  await h.screenshot({ path: path.join(OUT, 'human_test.jpg'), ...J }); console.log('saved human_test.jpg');

  // the executed notebook rendered by nbconvert
  const n = await b.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2 });
  await n.goto('file://' + path.join(OUT, 'notebook.html')); await n.waitForTimeout(800);
  const cells = n.locator('.jp-Cell');
  const pick = async (text, name, span) => {
    const count = await cells.count();
    for (let i = 0; i < count; i++) {
      if ((await cells.nth(i).innerText()).includes(text)) {
        const box1 = await cells.nth(i).boundingBox(), box2 = await cells.nth(Math.min(count - 1, i + span)).boundingBox();
        await n.screenshot({ path: path.join(OUT, name), fullPage: true, ...J,
          clip: { x: box1.x, y: box1.y, width: box1.width, height: box2.y + box2.height - box1.y } });
        console.log('saved', name); return;
      }
    }
    console.log('not found', text);
  };
  await pick('Build a scene and its twin', 'nb_build.jpg', 1);
  await pick('What the model sees', 'nb_styles.jpg', 1);
  await pick('Optional: ask Gemini', 'nb_gemini.jpg', 1);
  await b.close();
})();
