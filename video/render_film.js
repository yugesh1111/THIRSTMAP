// Render a film page frame by frame (deterministic: every frame is drawn at an exact time) and encode it with its
// narration.   node video/render_film.js video/build/full docs/video/thirstmap_film.mp4 [fps]
//              node video/render_film.js video/build/full --preview 3,40,90 out_dir   (still frames to look at)
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const { once } = require('events');
const path = require('path');

(async () => {
  const [dir, out, a3, a4] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + path.resolve(dir, 'film.html'));
  await p.evaluate(async () => { await document.fonts.ready;
    await Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; }))); });
  const T = await p.evaluate(() => TL.T);
  if (out === '--preview') {
    for (const t of a3.split(',').map(Number)) {
      await p.evaluate(t => renderAt(t), t);
      await p.screenshot({ path: path.join(a4, `frame_${String(t).padStart(6, '0')}.jpg`), type: 'jpeg', quality: 85 });
    }
    await b.close(); return;
  }
  const fps = +(a3 || 30), n = Math.ceil(T * fps);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
    '-i', path.join(dir, 'narration.wav'), '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
    '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', out],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await p.evaluate(t => renderAt(t), i / fps);
    const buf = await p.screenshot({ type: 'jpeg', quality: 93 });
    if (!ff.stdin.write(buf)) await once(ff.stdin, 'drain');
    if (i % 600 === 0) console.log(`${i}/${n} frames, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  }
  ff.stdin.end();
  await once(ff, 'close');
  await b.close();
  console.log(`done: ${out} (${T.toFixed(1)} s, ${n} frames, ${((Date.now() - t0) / 1000).toFixed(0)} s to render)`);
})();
