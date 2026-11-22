"""Build a self-contained demo page: image -> question -> each model's answer -> automatic ✓/✗ -> answer reveal.

Usage: python3 build_demo.py --dataset dataset --run results/<run> [--per-skill 6] --out demo
Open demo/index.html in a browser (no server needed).
"""
import argparse
import html
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image

from report import SKILL_LABEL, SKILL_ORDER


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--run", required=True)
    ap.add_argument("--per-skill", type=int, default=6)
    ap.add_argument("--out", default="demo")
    a = ap.parse_args()
    ds, run, out = Path(a.dataset), Path(a.run), Path(a.out)
    root = ds.resolve()
    tasks = {}
    for line in open(ds / "tasks.jsonl"):
        t = json.loads(line)
        tasks[t["task_id"]] = t
    answers = defaultdict(dict)
    for line in open(run / "responses.jsonl"):
        r = json.loads(line)
        if not r.get("error") and r["mode"] == "image":
            answers[r["task_id"]][r["model"]] = dict(raw=r.get("raw", "")[:400], parsed=r.get("parsed"),
                                                     correct=r["correct"], tags=r.get("tags", []))
    by_skill = defaultdict(list)
    for tid in answers:
        by_skill[tasks[tid]["skill"]].append(tid)
    rng = random.Random(0)
    chosen = []
    for sk in SKILL_ORDER:
        pool = sorted(by_skill.get(sk, []))
        rng.shuffle(pool)
        chosen += sorted(pool[: a.per_skill], key=lambda t: tasks[t]["level"])

    if out.exists():
        shutil.rmtree(out)
    (out / "img").mkdir(parents=True)
    items = []
    for tid in chosen:
        t = tasks[tid]
        names = {}
        for key in ("image", "reveal"):
            src = root / t[key]
            name = src.parent.name + "_" + src.stem + ".jpg"
            if not (out / "img" / name).exists():
                Image.open(src).convert("RGB").save(out / "img" / name, quality=85)
            names[key] = "img/" + name
        items.append(dict(id=tid, skill=SKILL_LABEL[t["skill"]], style=t["style"], level=t["level"],
                          question=t["question"], answer=t["answer"], image=names["image"],
                          reveal=names["reveal"], models=answers[tid]))
    (out / "index.html").write_text(PAGE.replace("__DATA__", html.escape(json.dumps(items), quote=False)))
    print(f"demo with {len(items)} tasks -> {out / 'index.html'}")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ThirstMap demo</title>
<style>
:root{--bg:#f6f5f2;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#e4e3df;--ok:#008300;--bad:#e34948;--acc:#2a78d6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121211;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#33332f;--ok:#0ca30c;--bad:#e66767;--acc:#3987e5}}
:root[data-theme="dark"]{--bg:#121211;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#33332f;--ok:#0ca30c;--bad:#e66767;--acc:#3987e5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:20px 16px 8px;max-width:1200px;margin:auto}h1{font-size:22px;margin:0 0 4px}header p{margin:0;color:var(--ink2)}
.bar{display:flex;flex-wrap:wrap;gap:8px;padding:12px 16px;max-width:1200px;margin:auto;align-items:center}
select,button{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
.stats{margin-left:auto;color:var(--ink2);font-size:14px}
main{max-width:1200px;margin:auto;padding:0 16px 40px;display:grid;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);overflow:hidden}
@media (max-width:820px){.card{grid-template-columns:1fr}}
.pic{position:relative;background:#000}.pic img{width:100%;display:block}
.pic button{position:absolute;left:10px;bottom:10px;background:rgba(0,0,0,.7);color:#fff;border:0}
.body{padding:16px;display:flex;flex-direction:column;gap:10px}
.meta{display:flex;gap:6px;flex-wrap:wrap}.chip{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--ink2)}
.q{font-weight:600}.gold{font-size:14px;color:var(--ink2)}.gold b{color:var(--ink)}
.ans{border-top:1px solid var(--line);padding-top:8px;display:grid;gap:6px}
.row{display:grid;grid-template-columns:22px minmax(0,1fr);gap:8px;align-items:start}
.mark{font-weight:700;font-size:16px}.ok{color:var(--ok)}.bad{color:var(--bad)}
.row small{color:var(--ink2);display:block}.tag{font-size:12px;color:var(--bad)}
</style></head><body>
<header><h1>ThirstMap: can AI trace water through the landscape?</h1>
<p>Each task: a generated image, a question, a reference answer computed by a water-flow simulation. Every model answer is scored automatically. Press “Show answer key” to see the truth.</p></header>
<div class="bar">
<select id="fs"><option value="">All skills</option></select>
<select id="fy"><option value="">All image styles</option><option>satellite</option><option>map</option><option>thermal</option></select>
<select id="fr"><option value="">All results</option><option value="bad">Only tasks a model got wrong</option></select>
<span class="stats" id="stats"></span></div>
<main id="list"></main>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
</script>
</body></html>"""

PAGE = PAGE.replace("""<script>
const DATA""", """<script id="data" type="application/json">__DATA__</script>
<script>
const DATA""").replace("</script>\n</body>", r"""
const fmt = v => Array.isArray(v) ? (v.length ? v.join(', ') : 'none') : (v === null || v === undefined ? '—' : String(v));
const fs = document.getElementById('fs'), fy = document.getElementById('fy'), fr = document.getElementById('fr');
[...new Set(DATA.map(d => d.skill))].forEach(s => { const o = document.createElement('option'); o.textContent = s; fs.appendChild(o); });
function render(){
  const L = document.getElementById('list'); L.innerHTML = '';
  let n = 0, right = 0, total = 0;
  DATA.filter(d => (!fs.value || d.skill === fs.value) && (!fy.value || d.style === fy.value)
     && (!fr.value || Object.values(d.models).some(m => !m.correct))).forEach(d => {
    n++;
    const c = document.createElement('article'); c.className = 'card';
    const rows = Object.entries(d.models).map(([name, m]) => { total++; if (m.correct) right++;
      return `<div class="row"><span class="mark ${m.correct ? 'ok' : 'bad'}">${m.correct ? '✓' : '✗'}</span>
      <div><b>${name}</b>: ${fmt(m.parsed)}${m.tags && m.tags.length ? ` <span class="tag">(${m.tags.join(', ')})</span>` : ''}
      <small>${(m.raw || '').replace(/</g,'&lt;').slice(0,160)}</small></div></div>`; }).join('');
    c.innerHTML = `<div class="pic"><img src="${d.image}" alt="${d.style} image for task" loading="lazy">
      <button>Show answer key</button></div>
      <div class="body"><div class="meta"><span class="chip">${d.skill}</span><span class="chip">${d.style}</span>
      <span class="chip">difficulty ${d.level}/5</span></div>
      <div class="q">${d.question}</div><div class="gold">Reference answer (from simulation): <b>${fmt(d.answer)}</b></div>
      <div class="ans">${rows}</div></div>`;
    const img = c.querySelector('img'), b = c.querySelector('button');
    b.onclick = () => { const on = img.src.endsWith(d.reveal); img.src = on ? d.image : d.reveal; b.textContent = on ? 'Show answer key' : 'Hide answer key'; };
    L.appendChild(c);
  });
  document.getElementById('stats').textContent = `${n} tasks · ${right}/${total} model answers correct`;
}
[fs, fy, fr].forEach(e => e.onchange = render); render();
</script>
</body>""")

if __name__ == "__main__":
    main()
