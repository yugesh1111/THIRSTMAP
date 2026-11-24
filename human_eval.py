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
                                    .replace("__N__", str(len(items))).replace("__SUBMIT__", a.submit_url))
    print(f"{len(items)} tasks -> {out / 'index.html'}")


def import_submissions(a):
    """Netlify form submissions -> human_eval/answers/<person>.json, keeping each person's most complete send."""
    import csv
    best = {}
    for f in a.files:
        txt = Path(f).read_text()
        if txt.lstrip().startswith(("[", "{")):
            js = json.loads(txt)
            rows = [r.get("data", r) for r in (js if isinstance(js, list) else js.get("submissions", [js]))]
        else:
            rows = list(csv.DictReader(txt.splitlines()))
        for r in rows:
            if r.get("bot-field") or not r.get("answers"):
                continue
            try:
                ans = json.loads(r["answers"])
            except ValueError:
                continue
            sid = r.get("sid") or r.get("name") or str(len(best))
            if sid not in best or len(ans) > len(best[sid]["answers"]):
                best[sid] = dict(name=(r.get("name") or "").strip() or f"anon-{sid[:6]}", answers=ans, done=r.get("done"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for sid, v in best.items():
        (out / f"{sid}.json").write_text(json.dumps(v))
    print(f"{len(best)} people ({sum(v['done'] == 'yes' for v in best.values())} finished), "
          f"{sum(len(v['answers']) for v in best.values())} answers -> {out}/")


def score_files(a):
    ds = Path(a.dataset)
    from thirstmap import errata
    bad = errata.load(ds)
    tasks = {t["task_id"]: t for t in map(json.loads, open(ds / "tasks.jsonl")) if t["task_id"] not in bad}
    rows = []
    import glob
    files = [f for pat in a.files for f in (sorted(glob.glob(pat)) or [pat])]   # Windows shells do not expand *.txt
    for f in files:
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
<p class="muted">You will see __N__ questions about generated landscape images, each about where water flows. Answer as carefully as you can, on your own: no help from other people, search engines or AI tools. There is no time limit; most people take 10 to 15 minutes, and you can stop whenever you like. Your answers are compared with a water-flow simulation to check that people can solve these tasks; only your initials (optional) and your answers are collected, and only your score is published, in a public hackathon project. Answers are sent to us automatically as you go (stored with our form host, Netlify). Your progress is saved in this browser if you close the page.</p>
<p><label>Your initials (optional): <input type="text" id="who" autocomplete="off" maxlength="12"></label></p>
<div class="bar"><i id="prog" style="width:0"></i></div><p class="muted" id="count"></p>
<div id="stage"></div>
<p id="early" hidden><button id="stop" style="background:transparent;color:var(--acc);border:1px solid var(--acc)">Finish now and send what I have</button></p></div>
<form name="thirstmap-answers" method="POST" data-netlify="true" netlify-honeypot="bot-field" hidden>
<input name="sid"><input name="name"><input name="done"><input name="count"><textarea name="answers"></textarea><input name="bot-field"></form>
<script id="data" type="application/json">__DATA__</script>
<script>
const T = JSON.parse(document.getElementById('data').textContent);
const SUBMIT = '__SUBMIT__';
let k = 0, t0 = Date.now(), finished = false; const answers = [];
let sid = Math.random().toString(36).slice(2) + Date.now().toString(36);
try { const saved = JSON.parse(localStorage.getItem('tm_human') || 'null'); if (saved) { answers.push(...saved.answers); k = answers.length; finished = !!saved.finished; sid = saved.sid || sid; document.getElementById('who').value = saved.name || ''; } } catch (e) {}
const who = () => document.getElementById('who').value.trim().slice(0, 12);
function save(){ try { localStorage.setItem('tm_human', JSON.stringify({name: who(), answers, finished, sid})); } catch (e) {} }
async function send(done){            // to the Netlify form; a later send from the same person replaces an earlier one
  const body = new URLSearchParams({'form-name': 'thirstmap-answers', sid, name: who(), done: done ? 'yes' : 'partial',
                                    count: String(answers.length), answers: JSON.stringify(answers), 'bot-field': ''});
  const same = location.origin === new URL(SUBMIT, location.href).origin;
  try {
    const r = await fetch(SUBMIT, {method: 'POST', mode: same ? 'same-origin' : 'no-cors',
                                   headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: body.toString()});
    return same ? r.ok : true;         // a send to another site cannot be read back; the backup below stays available
  } catch (e) { return false; }
}
document.getElementById('stop').onclick = () => { finished = true; save(); show(); };
function show(){
  document.getElementById('prog').style.width = (100 * k / T.length) + '%';
  document.getElementById('count').textContent = finished || k >= T.length ? `${answers.length} of ${T.length} answered` : `Task ${k + 1} of ${T.length}`;
  document.getElementById('early').hidden = finished || k >= T.length || answers.length === 0;
  const st = document.getElementById('stage');
  if (finished || k >= T.length) { finished = true; save(); const code = JSON.stringify({name: who(), answers});
    st.innerHTML = '<div class="card" style="display:block;padding:16px"><p id="sendmsg"><b>Sending your answers…</b></p>'
      + `<p class="muted">You answered ${answers.length} of ${T.length} questions.</p>`
      + '<details id="backup"><summary class="muted">Backup: copy or download your answers</summary>'
      + '<p style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px"><button id="cp">Copy my answers</button><button id="dl">Download my answers</button></p>'
      + '<p class="muted" id="cpmsg"></p><textarea id="code" readonly rows="5" style="width:100%;font:12px monospace"></textarea></details></div>';
    send(true).then(ok => { const m = document.getElementById('sendmsg');
      if (ok) m.innerHTML = '<b>Done, thank you! Your answers have been sent.</b>';
      else { m.innerHTML = '<b>Done, thank you!</b> Your answers could not be sent automatically. Please open the backup below and send them to the ThirstMap team.'; document.getElementById('backup').open = true; } });
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
    answers.push({id: d.id, answer: ans, seconds: (Date.now() - t0) / 1000}); k++; save();
    if (answers.length === 12 && k < T.length) send(false);     // one progress send, so a person who stops still counts
    show(); };
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
    b.add_argument("--submit-url", default="https://thirstmap-human-test.netlify.app/",
                   help="where the page sends answers (a Netlify site with form detection on)")
    i = sub.add_parser("import", help="form submissions (Netlify API JSON or dashboard CSV) -> one answers file per person")
    i.add_argument("files", nargs="+"); i.add_argument("--out", default="human_eval/answers")
    s = sub.add_parser("score"); s.add_argument("files", nargs="+"); s.add_argument("--dataset", default="dataset")
    s.add_argument("--run", default="results/models", help="compare with the models' answers to the same tasks")
    s.add_argument("--out", default="human_eval")
    a = ap.parse_args()
    {"build": build, "score": score_files, "import": import_submissions}[a.cmd](a)
