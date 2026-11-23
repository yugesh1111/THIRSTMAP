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
    from thirstmap import errata
    bad = errata.load(ds)
    tasks = [t for t in map(json.loads, open(ds / "tasks.jsonl")) if t["task_id"] not in bad]
    if a.from_run:      # only questions every model in that run answered, so humans and models share items
        ids = {t["task_id"] for t in tasks}
        per = defaultdict(set)
        for line in open(Path(a.from_run) / "responses.jsonl"):
            r = json.loads(line)
            if r["mode"] == "image" and not r.get("error") and not r["model"].startswith("mock:") and r["task_id"] in ids:
                per[r["model"]].add(r["task_id"])
        mx = max(len(v) for v in per.values())       # models still running are left out of the intersection
        common = set.intersection(*[v for v in per.values() if len(v) >= 0.8 * mx])
        tasks = [t for t in tasks if t["task_id"] in common]
    rng = random.Random(7)
    chosen = []
    if a.pairs:            # every complete before-and-after pair in the pool: humans get a pair score too
        halves = defaultdict(dict)
        for t in tasks:
            if t.get("pair_id"):
                halves[t["pair_id"]][t["variant"]] = t
        for pid in sorted(halves):
            if len(halves[pid]) == 2:
                chosen += [halves[pid]["base"], halves[pid]["counterfactual"]]
    have = {t["task_id"] for t in chosen}
    count = defaultdict(int)
    for t in chosen:
        count[t["skill"]] += 1
    by = defaultdict(list)
    for t in tasks:
        if t.get("variant") != "counterfactual" and t["task_id"] not in have:
            by[t["skill"]].append(t)
    for sk in SKILL_ORDER:                   # then fill every skill up to per_skill questions
        pool = by.get(sk, [])
        rng.shuffle(pool)
        chosen += pool[: max(0, a.per_skill - count[sk])]
    for _ in range(200):                     # shuffle so the two halves of a pair sit far apart
        rng.shuffle(chosen)
        pos = {t["task_id"]: k for k, t in enumerate(chosen)}
        gaps = [abs(pos[t["task_id"]] - pos[t["pair_id"].replace("__", "_cf__", 1)]) for t in chosen
                if t.get("variant") == "base" and t["pair_id"].replace("__", "_cf__", 1) in pos]
        if not gaps or min(gaps) >= 6:
            break
    if out.exists():
        for p in out.glob("img/*"):
            p.unlink()
    (out / "img").mkdir(parents=True, exist_ok=True)
    items = []
    for t in chosen:
        name = t["image"].replace("/", "_").replace(".png", ".jpg")
        Image.open(ds / t["image"]).convert("RGB").save(out / "img" / name, quality=88)
        ctx = t["prompt"].split("Question:")[0].strip()          # the same context line the models get
        items.append(dict(id=t["task_id"], img="img/" + name, q=t["question"], ctx=ctx, kind=t["scoring"],
                          options=t["options"], skill=SKILL_LABEL[t["skill"]], style=t["style"],
                          unit="m" if t["qid"] == "Q10" else "°C"))
    (out / "index.html").write_text(PAGE.replace("__DATA__", html.escape(json.dumps(items), quote=False))
                                    .replace("__N__", str(len(items))))
    print(f"{len(items)} tasks -> {out / 'index.html'}")


def score_files(a):
    ds = Path(a.dataset)
    from thirstmap import errata
    bad = errata.load(ds)
    tasks = {t["task_id"]: t for t in map(json.loads, open(ds / "tasks.jsonl")) if t["task_id"] not in bad}
    rows = []
    for f in a.files:
        txt = Path(f).read_text().strip()
        sub = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])      # tolerate text around a pasted code
        for r in sub["answers"]:
            t = tasks.get(r["id"])
            if t:
                s = score(t, json.dumps({"answer": r["answer"]}))
                rows.append(dict(person=sub.get("name") or Path(f).stem, skill=t["skill"], correct=s["correct"],
                                 seconds=r.get("seconds"), id=r["id"]))
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
    if a.run and (Path(a.run) / "responses.jsonl").exists():
        ids = {r["id"] for r in rows}
        got = defaultdict(dict)
        for line in open(Path(a.run) / "responses.jsonl"):
            r = json.loads(line)
            if r["mode"] == "image" and r["task_id"] in ids and not r.get("error") and not r["model"].startswith("mock:"):
                got[r["model"]][r["task_id"]] = score(tasks[r["task_id"]], r["raw"])["correct"]
        human = sum(r["correct"] for r in rows) / len(rows)
        L += ["", f"### Humans vs models on the same {len(ids)} questions", "",
              "| Who | Accuracy |", "|---|---|", f"| **Humans ({len(people)})** | **{100 * human:.0f}%** |"]
        for m, v in sorted(got.items(), key=lambda kv: -sum(kv[1].values()) / max(1, len(kv[1]))):
            if len(v) == len(ids):
                L.append(f"| {m.split(':', 1)[-1].split('@')[0].split('/')[-1]} | {100 * sum(v.values()) / len(v):.0f}% |")
    # before-and-after pairs: a person (or model) scores a pair only if both halves are right
    hp = []
    by_person = defaultdict(dict)
    for r in rows:
        by_person[r["person"]][r["id"]] = r["correct"]
    pair_ids = sorted({tasks[i]["pair_id"] for i in {r["id"] for r in rows} if tasks[i].get("pair_id")})
    pair_ids = [p_ for p_ in pair_ids if p_ in {r["id"] for r in rows} and p_.replace("__", "_cf__", 1) in {r["id"] for r in rows}]
    if pair_ids:
        hp = [by_person[pp][p_] and by_person[pp][p_.replace("__", "_cf__", 1)] for pp in by_person for p_ in pair_ids
              if p_ in by_person[pp] and p_.replace("__", "_cf__", 1) in by_person[pp]]
        L += ["", f"### Before-and-after pairs ({len(pair_ids)} pairs; a pair counts only if both halves are right)", "",
              "| Who | Pairs right |", "|---|---|", f"| **Humans ({len(people)})** | **{sum(hp)} of {len(hp)}** |"]
        if a.run and (Path(a.run) / "responses.jsonl").exists():
            for m, v in sorted(got.items()):
                both = [v[p_] and v[p_.replace("__", "_cf__", 1)] for p_ in pair_ids
                        if p_ in v and p_.replace("__", "_cf__", 1) in v]
                if len(both) == len(pair_ids):
                    L.append(f"| {m.split(':', 1)[-1].split('@')[0].split('/')[-1]} | {sum(both)} of {len(both)} |")
    secs = [r["seconds"] for r in rows if r.get("seconds")]
    if secs:
        L += ["", f"Median time per task: {sorted(secs)[len(secs) // 2]:.0f} s"]
    Path(a.out).mkdir(exist_ok=True)
    (Path(a.out) / "HUMAN_RESULTS.md").write_text("\n".join(L))
    (Path(a.out) / "human_summary.json").write_text(json.dumps(dict(
        people=len(people), answers=len(rows), accuracy=sum(r["correct"] for r in rows) / len(rows),
        questions=len({r["id"] for r in rows}), pairs_right=sum(hp), pairs_answered=len(hp)), indent=1))
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
<p class="muted">You will see __N__ questions about generated landscape images, each about where water flows. Answer as carefully as you can, on your own: no help from other people, search engines or AI tools. There is no time limit; most people take 10 to 15 minutes. Your answers are compared with a water-flow simulation to check that people can solve these tasks; only your initials and your score are used, in a public hackathon project. Your progress is saved in this browser if you close the page.</p>
<p><label>Your initials: <input type="text" id="who" autocomplete="off"></label></p>
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
  if (k >= T.length) { const code = JSON.stringify({name: document.getElementById('who').value, answers});
    st.innerHTML = '<div class="card" style="display:block;padding:16px"><p><b>Done, thank you!</b> Send your answers to the ThirstMap team: press <b>Copy my answers</b> and paste them into a message (or download them as a file).</p>'
      + '<p style="display:flex;gap:8px;flex-wrap:wrap"><button id="cp">Copy my answers</button><button id="dl">Download my answers</button></p>'
      + '<p class="muted" id="cpmsg"></p><textarea id="code" readonly rows="5" style="width:100%;font:12px monospace"></textarea></div>';
    document.getElementById('code').value = code;
    document.getElementById('cp').onclick = () => { const ta = document.getElementById('code'), m = document.getElementById('cpmsg');
      navigator.clipboard.writeText(code).then(() => { m.textContent = 'Copied. Paste it into a message to the team.'; },
        () => { ta.focus(); ta.select(); m.textContent = 'Press Ctrl+C (or long-press and Copy) to copy the selected text.'; }); };
    document.getElementById('dl').onclick = () => { const b = new Blob([JSON.stringify({name: document.getElementById('who').value, answers}, null, 1)], {type: 'application/json'});
      const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'answers_' + (document.getElementById('who').value || 'anon').replace(/\W+/g, '_') + '.json'; a.click(); };
    return; }
  const d = T[k]; let inp = '';
  if (d.kind === 'set') inp = '<div class="opts">' + d.options.map(o => `<label><input type="checkbox" value="${o}"> ${o}</label>`).join('') + '</div><p class="muted">Tick all that apply (none is allowed).</p>';
  else if (d.kind === 'number') inp = `<input type="number" step="0.1" id="num"> ${d.unit}`;
  else inp = '<div class="opts">' + d.options.map(o => `<label><input type="radio" name="r" value="${o}"> ${o}</label>`).join('') + '</div>';
  st.innerHTML = `<div class="card"><a href="${d.img}" target="_blank" rel="noopener" title="Open the image full size">
    <img src="${d.img}" alt="${d.style} image for this question"></a><div class="side">
    <span class="muted">${d.ctx || (d.style + ' image')} Tap or click the image to open it full size.</span>
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
    b.add_argument("--from-run", default=None, help="pick only tasks every model in this run answered")
    b.add_argument("--pairs", action="store_true", help="include every complete before-and-after pair in the pool")
    s = sub.add_parser("score"); s.add_argument("files", nargs="+"); s.add_argument("--dataset", default="dataset")
    s.add_argument("--run", default="results/models", help="compare with the models' answers to the same tasks")
    s.add_argument("--out", default="human_eval")
    a = ap.parse_args()
    build(a) if a.cmd == "build" else score_files(a)
