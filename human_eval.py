"""Human baseline (V15): can people solve the tasks? Same tasks, same scorer as the AI models.

  python3 human_eval.py build --dataset dataset --per-skill 3 --out human_eval
      -> human_eval/index.html (self-contained; open it, answer, press "Download my answers")
  python3 human_eval.py score human_eval/answers_*.json --dataset dataset
      -> per-skill human accuracy, written to human_eval/HUMAN_RESULTS.md
"""
import argparse
import html
import json
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

from report import SKILL_LABEL, SKILL_ORDER
from thirstmap.scoring import score


def build(a):
    ds, out = Path(a.dataset), Path(a.out)
    tasks = [json.loads(l) for l in open(ds / "tasks.jsonl")]
    rng = random.Random(7)
    by = defaultdict(list)
    for t in tasks:
        if t.get("variant") != "counterfactual":
            by[t["skill"]].append(t)
    chosen = []
    for sk in SKILL_ORDER:
        pool = by.get(sk, [])
        rng.shuffle(pool)
        chosen += pool[: a.per_skill]
    rng.shuffle(chosen)
    if out.exists():
        for p in out.glob("img/*"):
            p.unlink()
    (out / "img").mkdir(parents=True, exist_ok=True)
    items = []
    for t in chosen:
        name = t["image"].replace("/", "_").replace(".png", ".jpg")
        Image.open(ds / t["image"]).convert("RGB").save(out / "img" / name, quality=88)
        items.append(dict(id=t["task_id"], img="img/" + name, q=t["question"], kind=t["scoring"],
                          options=t["options"], skill=SKILL_LABEL[t["skill"]], style=t["style"],
                          unit="m" if t["qid"] == "Q10" else "°C"))
    (out / "index.html").write_text(PAGE.replace("__DATA__", html.escape(json.dumps(items), quote=False)))
    print(f"{len(items)} tasks -> {out / 'index.html'}")


def score_files(a):
    ds = Path(a.dataset)
    tasks = {json.loads(l)["task_id"]: json.loads(l) for l in open(ds / "tasks.jsonl")}
    rows = []
    for f in a.files:
        sub = json.loads(Path(f).read_text())
        for r in sub["answers"]:
            t = tasks.get(r["id"])
            if t:
                s = score(t, json.dumps({"answer": r["answer"]}))
                rows.append(dict(person=sub.get("name", Path(f).stem), skill=t["skill"], correct=s["correct"],
                                 seconds=r.get("seconds")))
    if not rows:
        sys.exit("no matching answers")
    by = defaultdict(list)
    for r in rows:
        by[r["skill"]].append(r["correct"])
    people = sorted({r["person"] for r in rows})
    L = ["# Human baseline (V15)", "", f"{len(people)} people, {len(rows)} answers. Same tasks and scorer as the models.", "",
         f"**Overall human accuracy: {100 * sum(r['correct'] for r in rows) / len(rows):.0f}%**", "",
         "| Skill | Human accuracy | Answers |", "|---|---|---|"]
    for sk in SKILL_ORDER:
        if sk in by:
            L.append(f"| {SKILL_LABEL[sk]} | {100 * sum(by[sk]) / len(by[sk]):.0f}% | {len(by[sk])} |")
    secs = [r["seconds"] for r in rows if r.get("seconds")]
    if secs:
        L += ["", f"Median time per task: {sorted(secs)[len(secs) // 2]:.0f} s"]
    Path(a.out).mkdir(exist_ok=True)
    (Path(a.out) / "HUMAN_RESULTS.md").write_text("\n".join(L))
    print("\n".join(L))


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ThirstMap human test</title>
<style>
:root{--bg:#f6f5f2;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#e4e3df;--acc:#2a78d6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121211;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#33332f;--acc:#3987e5}}
:root[data-theme="dark"]{--bg:#121211;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#33332f;--acc:#3987e5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
.wrap{max-width:1100px;margin:auto;padding:16px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);overflow:hidden}@media(max-width:820px){.card{grid-template-columns:1fr}}
img{width:100%;display:block}.side{padding:16px;display:flex;flex-direction:column;gap:12px}
.opts{display:flex;flex-wrap:wrap;gap:8px}.opts label{border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer}
input[type=number],input[type=text]{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);width:10em}
button{font:inherit;padding:8px 14px;border-radius:8px;border:0;background:var(--acc);color:#fff;cursor:pointer}
.muted{color:var(--ink2);font-size:14px}.bar{height:6px;background:var(--line);border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
</style></head><body><div class="wrap">
<h1 style="font-size:22px;margin:4px 0">Can you trace the water?</h1>
<p class="muted">You will see generated landscape images and questions. Answer as carefully as you can, without help. Your answers are compared with a water-flow simulation to check the tasks are solvable by people.</p>
<p><label>Your name or initials: <input type="text" id="who"></label></p>
<div class="bar"><i id="prog" style="width:0"></i></div><p class="muted" id="count"></p>
<div id="stage"></div></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const T = JSON.parse(document.getElementById('data').textContent);
let k = 0, t0 = Date.now(); const answers = [];
try { const saved = JSON.parse(localStorage.getItem('tm_human') || 'null'); if (saved) { answers.push(...saved.answers); k = answers.length; document.getElementById('who').value = saved.name || ''; } } catch (e) {}
function save(){ try { localStorage.setItem('tm_human', JSON.stringify({name: document.getElementById('who').value, answers})); } catch (e) {} }
function show(){
  document.getElementById('prog').style.width = (100 * k / T.length) + '%';
  document.getElementById('count').textContent = `Task ${Math.min(k + 1, T.length)} of ${T.length}`;
  const st = document.getElementById('stage');
  if (k >= T.length) { st.innerHTML = '<div class="card" style="display:block;padding:16px"><p><b>Done, thank you!</b></p><button id="dl">Download my answers</button></div>';
    document.getElementById('dl').onclick = () => { const b = new Blob([JSON.stringify({name: document.getElementById('who').value, answers}, null, 1)], {type: 'application/json'});
      const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'answers_' + (document.getElementById('who').value || 'anon').replace(/\W+/g, '_') + '.json'; a.click(); };
    return; }
  const d = T[k]; let inp = '';
  if (d.kind === 'set') inp = '<div class="opts">' + d.options.map(o => `<label><input type="checkbox" value="${o}"> ${o}</label>`).join('') + '</div><p class="muted">Tick all that apply (none is allowed).</p>';
  else if (d.kind === 'number') inp = `<input type="number" step="0.1" id="num"> ${d.unit}`;
  else inp = '<div class="opts">' + d.options.map(o => `<label><input type="radio" name="r" value="${o}"> ${o}</label>`).join('') + '</div>';
  st.innerHTML = `<div class="card"><img src="${d.img}" alt="task image"><div class="side"><span class="muted">${d.style} image</span>
    <b>${d.q}</b>${inp}<button id="next">Next</button></div></div>`;
  t0 = Date.now();
  document.getElementById('next').onclick = () => {
    let ans;
    if (d.kind === 'set') ans = [...st.querySelectorAll('input:checked')].map(e => e.value);
    else if (d.kind === 'number') { const v = document.getElementById('num').value; if (v === '') return; ans = parseFloat(v); }
    else { const e = st.querySelector('input:checked'); if (!e) return; ans = e.value; }
    answers.push({id: d.id, answer: ans, seconds: (Date.now() - t0) / 1000}); k++; save(); show(); };
}
show();
</script></body></html>"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--dataset", default="dataset")
    b.add_argument("--per-skill", type=int, default=3); b.add_argument("--out", default="human_eval")
    s = sub.add_parser("score"); s.add_argument("files", nargs="+"); s.add_argument("--dataset", default="dataset")
    s.add_argument("--out", default="human_eval")
    a = ap.parse_args()
    build(a) if a.cmd == "build" else score_files(a)
