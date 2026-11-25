"""The ThirstMap leaderboard as a product page: docs/leaderboard/.

    python3 build_leaderboard.py --dataset dataset --runs results/frontier results/frontier_pairs

Writes a page that re-scores every published reply in the browser (docs/leaderboard/score.js, a port of
thirstmap/scoring.py checked against it reply by reply), shows a report card per model, and lets anyone score their own
model: download the question pack, run the model anywhere, drop the replies on the page. Nothing is uploaded.
"""
import argparse
import io
import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

from frontier import batch_prompt

OUT = Path("docs/leaderboard")
KEEP = ("task_id", "scene_id", "qid", "skill", "style", "level", "terrain", "question", "options", "scoring", "tolerance",
        "answer", "traps", "pair_id", "variant", "cf_kind")
NAMES = {"openai:gemini-3.5-flash": "Gemini 3.5 Flash", "openai:gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
         "openai:gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite", "hf:Qwen/Qwen2.5-VL-3B-Instruct": "Qwen2.5-VL-3B",
         "hf:Qwen/Qwen2-VL-2B-Instruct": "Qwen2-VL-2B"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--runs", nargs="+", default=["results/frontier", "results/frontier_pairs"])
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    from thirstmap import errata
    ds, out = Path(a.dataset), Path(a.out)
    bad = errata.load(ds)
    tasks = {t["task_id"]: t for t in map(json.loads, open(ds / "tasks.jsonl")) if t["task_id"] not in bad}
    (out / "img").mkdir(parents=True, exist_ok=True)
    images, packed, resp, tok = [], {}, defaultdict(lambda: defaultdict(dict)), defaultdict(lambda: [0, 0])
    for run in map(Path, a.runs):
        S = json.loads((run / "set.json").read_text())
        for img in S["images"]:
            ids = [i for i in img["tasks"] if i in tasks]
            if not ids:
                continue
            Image.open(run / img["file"]).convert("RGB").save(out / "img" / f"{img['image']}.jpg", quality=86)
            images.append(dict(key=img["image"], set=run.name, tasks=ids))
            packed[img["image"]] = (run / img["file"], [tasks[i] for i in ids])
        for line in (open(run / "responses.jsonl") if (run / "responses.jsonl").exists() else []):
            r = json.loads(line)
            if r["task_id"] in tasks and r["model"] in NAMES and r.get("raw") is not None:
                resp[r["model"]][r["mode"]][r["task_id"]] = r["raw"]
        if (run / "requests.jsonl").exists():
            for line in open(run / "requests.jsonl"):
                r = json.loads(line)
                if not r.get("error") and r.get("input_tokens") and r.get("mode", "image") == "image" and r["model"] in NAMES:
                    tok[r["model"]][0] += r["input_tokens"] + (r.get("output_tokens") or 0)
                    tok[r["model"]][1] += r.get("questions", 0)
    in_pack = {i for im in images for i in im["tasks"]}
    data = dict(version="frontier-pack-v1", sets=[Path(r).name for r in a.runs], images=images,
                tasks=[{k: tasks[i].get(k) for k in KEEP} for i in sorted(in_pack)],
                models=[dict(id=m, name=NAMES[m], kind="open, local" if m.startswith("hf:") else "API",
                             tokens_per_answer=round(tok[m][0] / tok[m][1]) if tok[m][1] else None,
                             replies={mode: {k: v for k, v in d.items() if k in in_pack} for mode, d in resp[m].items()})
                        for m in NAMES if m in resp])
    (out / "data.json").write_text(json.dumps(data, separators=(",", ":")))

    # the question pack: images, questions without answers, the batched prompt per image, reply formats
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for key, (src, ts) in packed.items():
            z.write(src, f"thirstmap_pack/images/{key}.png")
        z.writestr("thirstmap_pack/questions.jsonl", "".join(
            json.dumps(dict(task_id=t["task_id"], image=f"images/{img['key']}.png", question=t["question"], options=t["options"],
                            answer_format=t["scoring"], skill=t["skill"], prompt=t["prompt"])) + "\n"
            for img in images for t in (tasks[i] for i in img["tasks"])))
        z.writestr("thirstmap_pack/prompts_batched.jsonl", "".join(
            json.dumps(dict(image=f"images/{k}.png", prompt=batch_prompt(ts))) + "\n" for k, (_, ts) in packed.items()))
        z.writestr("thirstmap_pack/README.md", PACK_README.replace("__N__", str(len(in_pack))).replace("__I__", str(len(images))))
    (out / "thirstmap_frontier_pack_v1.zip").write_bytes(buf.getvalue())
    sample = [json.dumps(dict(image=k, raw=v)) for k, v in _batched_raws("results/frontier", "openai:gemini-3.1-flash-lite")
              if k in packed]
    (out / "sample_replies.jsonl").write_text("\n".join(sample) + "\n")
    shutil.copy(Path(__file__).with_name("docs") / "leaderboard" / "score.js", out / "score.js") \
        if out != OUT else None
    (out / "index.html").write_text(PAGE)
    print(f"{len(images)} images, {len(in_pack)} questions, {len(data['models'])} models -> {out}/index.html "
          f"(pack {len(buf.getvalue()) // 1024} KB)")


def _batched_raws(run, model):
    for line in open(Path(run) / "requests.jsonl"):
        r = json.loads(line)
        if r["model"] == model and r.get("mode", "image") == "image" and not r.get("error"):
            yield r["image"], r["raw"]


PACK_README = """# ThirstMap frontier pack v1

__I__ images and __N__ questions from the ThirstMap benchmark (https://github.com/yugesh1111/THIRSTMAP), including
before-and-after twins: the same scene with one change that flips the answer. The answers are public in the repository;
this is a diagnostic benchmark, not a hidden test.

- `images/`: the exact 768 px images every model on the leaderboard saw
- `questions.jsonl`: one question per line, with its options, answer format and the full single-question prompt
- `prompts_batched.jsonl`: one prompt per image that asks every question about it at once (what the leaderboard used)

Send each image with its prompt to your model, then save the replies as JSON Lines in any of these forms and drop the
file on https://yugesh1111.github.io/THIRSTMAP/leaderboard/ (it is scored in your browser; nothing is uploaded):

    {"image": "level2_seed22760__map", "raw": "<the model's whole reply to the batched prompt>"}
    {"task_id": "level2_seed22760__Q1__map", "raw": "<the model's reply to the single-question prompt>"}
    {"task_id": "level2_seed22760__Q1__map", "answer": ["V3", "V5"]}

Add "model": "<name>" to every line to score several models from one file. Or score with the Python package:
`thirstmap evaluate --models openai:MODEL@BASE_URL ...` (see the repository README).
"""

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ThirstMap leaderboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#f3f6f7;--surface:#fff;--ink:#0f1417;--ink2:#4b5860;--line:#d9e1e5;--water:#2a78d6;--waste:#d95926;--ok:#0b7a0b;--bad:#c13a3a;--chip:#eaf0f3;
--display:"Space Grotesk",ui-sans-serif,system-ui,sans-serif;--text:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;--mono:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e1316;--surface:#161c20;--ink:#eef2f4;--ink2:#a7b3ba;--line:#2a343a;--water:#3987e5;--waste:#e2703f;--ok:#34b334;--bad:#e66767;--chip:#1f272c;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0e1316;--surface:#161c20;--ink:#eef2f4;--ink2:#a7b3ba;--line:#2a343a;--water:#3987e5;--waste:#e2703f;--ok:#34b334;--bad:#e66767;--chip:#1f272c;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--text)}
.wrap{max-width:1180px;margin:0 auto;padding-block:28px 56px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
h1{font:700 34px/1.15 var(--display);margin:6px 0 6px;text-wrap:balance}h2{font:700 24px/1.2 var(--display);margin:40px 0 10px}
h3{font:700 18px var(--display);margin:0 0 8px}.eyebrow{font:600 12px var(--text);letter-spacing:.14em;text-transform:uppercase;color:var(--water)}
.lede{color:var(--ink2);max-width:72ch;margin:0}a{color:var(--water)}
.nav{display:flex;flex-wrap:wrap;gap:6px 16px;margin:14px 0 0;font-size:14px}
.views{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 12px}.views button{font:600 13px var(--text);border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:999px;padding:6px 14px;cursor:pointer}
.views button[aria-pressed="true"]{background:var(--water);border-color:var(--water);color:#fff}
.tablewrap{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:14px}
table{border-collapse:collapse;width:100%;min-width:860px;font-variant-numeric:tabular-nums}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}th{font:600 12px var(--text);color:var(--ink2);text-transform:uppercase;letter-spacing:.06em}
tr:last-child td{border-bottom:0}tbody tr{cursor:pointer}tbody tr:hover{background:var(--chip)}tr.yours td{background:color-mix(in srgb,var(--waste) 9%,transparent)}
.rank{font:700 18px var(--display);width:40px}.mname b{display:block}.mname span{font-size:12px;color:var(--ink2)}
.acc{display:flex;align-items:center;gap:10px;min-width:220px}.bar{position:relative;flex:1;height:12px;background:var(--chip);border-radius:6px}
.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:6px;background:var(--water)}.bar b{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--ink)}
.acc strong{font:700 17px var(--display);width:46px}.dim{color:var(--ink2)}.good{color:var(--ok)}.bad{color:var(--bad)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;margin-top:16px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:10px 0 16px}
.stat{background:var(--chip);border-radius:10px;padding:10px 12px}.stat b{display:block;font:700 24px var(--display)}.stat span{font-size:12.5px;color:var(--ink2)}
.skills{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:6px 24px}
.sk{display:grid;grid-template-columns:150px 1fr 42px;gap:8px;align-items:center;font-size:13px}
.pairs{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-top:8px}
.pair{border:1px solid var(--line);border-radius:10px;padding:8px;font-size:12.5px}.pair .ims{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.pair img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;display:block}.pair .v{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px}
.mist{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px;margin-top:8px}
.m{display:grid;grid-template-columns:110px 1fr;gap:10px;border:1px solid var(--line);border-radius:10px;padding:8px;font-size:12.5px;min-width:0}
.m img{width:110px;height:110px;object-fit:cover;border-radius:6px}.m p{margin:0 0 4px}.tag{display:inline-block;font:600 11px var(--mono);background:var(--chip);border-radius:6px;padding:1px 6px;margin:2px 4px 0 0}
.drop{border:2px dashed var(--line);border-radius:14px;padding:22px;text-align:center;background:var(--surface)}
.drop.over{border-color:var(--water);background:color-mix(in srgb,var(--water) 8%,var(--surface))}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:10px;align-items:start}
.step{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;min-width:0}
pre{font:12.5px/1.5 var(--mono);background:var(--chip);border-radius:8px;padding:10px;overflow-x:auto;margin:8px 0 0;white-space:pre}
.btn{display:inline-block;font:600 14px var(--text);background:var(--water);color:#fff;border:0;border-radius:10px;padding:9px 16px;cursor:pointer;text-decoration:none}
.btn.ghost{background:transparent;color:var(--water);border:1px solid var(--water)}
.note{font-size:13px;color:var(--ink2);margin-top:10px}#msg{margin-top:10px;font-weight:600}
button:focus-visible,a:focus-visible,tr:focus-visible{outline:3px solid var(--waste);outline-offset:2px}
</style></head><body><div class="wrap">
<p class="eyebrow">ThirstMap · frontier pack v1</p>
<h1>Leaderboard: who can trace the water?</h1>
<p class="lede">Every model got the same images and the same prompts. Every reply below is scored again in your browser by the same rules as the Python scorer (they agree on all 37,516 published replies). Chance is the exact probability of guessing each question; <b>pairs</b> are before-and-after twins, right only if both halves are right.</p>
<p class="nav"><a href="../">Live demo</a><a href="../film.html">The film</a><a href="../human/">Take the test yourself</a><a href="https://github.com/yugesh1111/THIRSTMAP">Code and data</a><a href="#yours">Score your own model</a></p>
<div class="views" role="group" aria-label="Question set">
<button data-view="all" aria-pressed="true">All images</button><button data-view="frontier" aria-pressed="false">Frontier set</button><button data-view="frontier_pairs" aria-pressed="false">Pair extension</button></div>
<div class="tablewrap"><table><thead><tr><th>#</th><th>Model</th><th>Correct (line: chance)</th><th>Chance</th><th>p (beats chance)</th><th>Pairs right</th><th>Without image</th><th>Fell for a trap</th><th>Tokens / answer</th></tr></thead>
<tbody id="board"><tr><td colspan="9" class="dim">Loading and scoring every reply…</td></tr></tbody></table></div>
<p class="note" id="basis"></p>
<div id="cardslot"></div>

<h2 id="yours">Score your own model</h2>
<p class="lede">Run any model on the pack, then drop its replies here. You get the same report card and a place on the board. Scoring happens on this page; the file never leaves your computer.</p>
<div class="steps">
<div class="step"><h3>1 · Get the questions</h3><p class="dim">The exact images, the prompts and the reply formats.</p><a class="btn" href="thirstmap_frontier_pack_v1.zip" download>Download the pack</a></div>
<div class="step"><h3>2 · Run your model</h3><p class="dim">Save one JSON object per line, in any of these forms:</p>
<pre>{"image": "level2_seed22760__map", "raw": "&lt;whole reply&gt;"}
{"task_id": "…__Q1__map", "raw": "&lt;reply&gt;"}
{"task_id": "…__Q1__map", "answer": ["V3", "V5"]}</pre></div>
<div class="step"><h3>3 · Drop the file</h3><div class="drop" id="drop"><p><b>Drop a .jsonl file here</b></p><p><label class="btn ghost">Choose a file<input type="file" id="file" accept=".jsonl,.json,.txt" hidden></label></p>
<p><button class="btn ghost" id="sample">Try a sample file</button></p></div><p id="msg" aria-live="polite"></p></div>
</div>
</div>
<script src="score.js"></script>
<script>
const $ = s => document.querySelector(s), esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = x => x == null ? '–' : Math.round(100 * x) + '%';
const pfmt = p => p >= 0.01 ? p.toFixed(2) : p.toExponential(0).replace('e-', 'e-');
const SKILL = {trace_downstream:'Trace downstream',order_along_flow:'Order along the flow',measure_along_flow:'Distance along a river',
  nature_based_filtering:'Wetland placement',siting_downstream_impact:'Siting impact',read_elevation:'Read elevation',read_flow_direction:'Flow direction',
  trace_upstream_catchment:'Upstream catchment',read_colour_scale_threshold:'Colour-scale threshold',read_colour_scale_value:'Colour-scale value'};
let D, T, IMG = {}, view = 'all', yours = [], open = null;
const inView = id => view === 'all' || IMG[T[id].img] === view;

function card(m) {                                        // every number on the board comes from here
  const img = m.replies.image || {}, ids = Object.keys(img).filter(id => T[id] && inView(id));
  const rows = ids.map(id => ({t: T[id], s: TMScore.score(T[id], img[id])}));
  const n = rows.length, k = rows.filter(r => r.s.correct).length, c = n ? rows.reduce((a, r) => a + TMScore.chance(r.t), 0) / n : 0;
  const skills = {};
  for (const r of rows) { const s = skills[r.t.skill] ||= {k: 0, n: 0, c: 0}; s.n++; s.k += r.s.correct; s.c += TMScore.chance(r.t); }
  const by = Object.fromEntries(rows.map(r => [r.t.task_id, r]));
  const pairs = rows.filter(r => r.t.variant === 'counterfactual' && by[r.t.pair_id]).map(r => ({base: by[r.t.pair_id], twin: r,
    same: JSON.stringify(by[r.t.pair_id].s.parsed) === JSON.stringify(r.s.parsed)}));
  const exposed = rows.filter(r => r.t.traps && Object.keys(r.t.traps).length), fell = exposed.filter(r => r.s.tags.some(g => g.startsWith('trap:')));
  const bl = m.replies.blind || {}, bids = Object.keys(bl).filter(id => T[id] && inView(id));
  const blind = bids.length ? bids.filter(id => TMScore.score(T[id], bl[id]).correct).length / bids.length : null;
  return {m, n, k, acc: n ? k / n : 0, c, p: n ? TMScore.binomGreater(k, n, c) : 1, skills, pairs, pairsRight: pairs.filter(p => p.base.s.correct && p.twin.s.correct).length,
    trap: exposed.length ? fell.length / exposed.length : null, blind, bn: bids.length, wrong: rows.filter(r => !r.s.correct), total: Object.keys(T).filter(inView).length};
}
function board() {
  const cards = [...D.models.map(card), ...yours.map(card)].sort((a, b) => b.acc - a.acc);
  $('#board').innerHTML = cards.map((x, i) => `<tr tabindex="0" data-id="${esc(x.m.id)}" class="${x.m.yours ? 'yours' : ''}">
    <td class="rank">${i + 1}</td><td class="mname"><b>${esc(x.m.name)}</b><span>${esc(x.m.kind)}${x.n < x.total ? ` · answered ${x.n} of ${x.total}` : ''}</span></td>
    <td><div class="acc"><strong>${pct(x.acc)}</strong><div class="bar"><i style="width:${100 * x.acc}%"></i><b style="left:${100 * x.c}%"></b></div><span class="dim">${x.k}/${x.n}</span></div></td>
    <td>${pct(x.c)}</td><td class="${x.p < 0.05 ? 'good' : 'dim'}">${pfmt(x.p)}</td>
    <td><b class="${x.pairsRight ? '' : 'bad'}">${x.pairsRight} of ${x.pairs.length}</b></td>
    <td>${x.blind == null ? '<span class="dim">–</span>' : pct(x.blind) + ` <span class="dim">(${x.bn})</span>`}</td><td>${pct(x.trap)}</td>
    <td>${x.m.tokens_per_answer ?? '<span class="dim">–</span>'}</td></tr>`).join('');
  document.querySelectorAll('#board tr').forEach(tr => { tr.onclick = tr.onkeydown = e => { if (e.type === 'keydown' && e.key !== 'Enter') return;
    open = tr.dataset.id === open ? null : tr.dataset.id; showCard(cards); }; });
  const t = Object.keys(T).filter(inView).length, ims = D.images.filter(i => view === 'all' || i.set === view);
  $('#basis').textContent = `${ims.length} images, ${t} questions, ${ims.filter(i => i.key.includes('_cf__')).length} before-and-after pairs in this view. Click a model for its report card.`;
  showCard(cards);
}
function showCard(cards) {
  const x = cards.find(c => c.m.id === open);
  if (!x) { $('#cardslot').innerHTML = ''; return; }
  const sk = Object.entries(x.skills).map(([s, v]) => `<div class="sk"><span>${esc(SKILL[s] || s)}</span><div class="bar"><i style="width:${100 * v.k / v.n}%"></i><b style="left:${100 * v.c / v.n}%"></b></div><span>${v.k}/${v.n}</span></div>`).join('');
  const fmt = v => Array.isArray(v) ? (v.length ? v.join(', ') : 'none') : v == null ? 'no answer' : v;
  const pr = x.pairs.map(p => `<div class="pair"><div class="ims"><img src="img/${esc(T[p.base.t.task_id].img)}.jpg" alt="original"><img src="img/${esc(T[p.twin.t.task_id].img)}.jpg" alt="twin"></div>
    <div class="v"><span class="${p.base.s.correct ? 'good' : 'bad'}">${p.base.s.correct ? '✓' : '✗'} said ${esc(fmt(p.base.s.parsed))} · key ${esc(fmt(p.base.t.answer))}</span>
    <span class="${p.twin.s.correct ? 'good' : 'bad'}">${p.twin.s.correct ? '✓' : '✗'} said ${esc(fmt(p.twin.s.parsed))} · key ${esc(fmt(p.twin.t.answer))}</span></div>
    ${p.same && !p.twin.s.correct ? '<span class="tag">same answer to both</span>' : ''}</div>`).join('');
  const mi = x.wrong.slice(0, 12).map(r => `<div class="m"><img src="img/${esc(T[r.t.task_id].img)}.jpg" alt="" loading="lazy"><div style="min-width:0"><p>${esc(r.t.question)}</p>
    <p><b class="bad">said ${esc(fmt(r.s.parsed))}</b> · key ${esc(fmt(r.t.answer))}</p>${r.s.tags.map(g => `<span class="tag">${esc(g)}</span>`).join('')}</div></div>`).join('');
  $('#cardslot').innerHTML = `<div class="card"><p class="eyebrow">Report card</p><h2 style="margin-top:4px">${esc(x.m.name)}</h2>
    <div class="stats"><div class="stat"><b>${pct(x.acc)}</b><span>${x.k} of ${x.n} right</span></div><div class="stat"><b>${pct(x.c)}</b><span>chance on the same questions</span></div>
    <div class="stat"><b>${pfmt(x.p)}</b><span>p, one-sided binomial: beats chance?</span></div><div class="stat"><b>${x.pairsRight} of ${x.pairs.length}</b><span>pairs right on both halves</span></div>
    <div class="stat"><b>${x.blind == null ? '–' : pct(x.blind)}</b><span>${x.blind == null ? 'no-image control not run' : `without the image (${x.bn} questions)`}</span></div><div class="stat"><b>${pct(x.trap)}</b><span>fell for a built-in trap</span></div></div>
    <h3>Skills (bar: correct, line: chance)</h3><div class="skills">${sk}</div>
    <h3 style="margin-top:18px">Before-and-after pairs</h3><div class="pairs">${pr || '<p class="dim">No complete pair in this view.</p>'}</div>
    <h3 style="margin-top:18px">Mistakes (${x.wrong.length}, first 12)</h3><div class="mist">${mi || '<p class="dim">None.</p>'}</div></div>`;
}
function ingest(text, label) {
  const groups = {};
  let used = 0, skipped = 0;
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    let o; try { o = JSON.parse(line); } catch (e) { skipped++; continue; }
    const name = o.model || label, g = groups[name] ||= {image: {}}, mode = o.mode === 'blind' ? 'blind' : 'image';
    g[mode] ||= {};
    if (o.image && o.raw != null) { const im = D.images.find(i => i.key === o.image || i.key === String(o.image).replace(/^.*\//, '').replace(/\.(png|jpe?g)$/, ''));
      if (!im) { skipped++; continue; } const obj = TMScore.parseBatch(o.raw);
      for (const id of im.tasks) { const q = T[id].qid; g[mode][id] = q in obj ? JSON.stringify({answer: obj[q]}) : ''; used++; } }
    else if (o.task_id && T[o.task_id]) { g[mode][o.task_id] = o.raw != null ? String(o.raw) : JSON.stringify({answer: o.answer}); used++; }
    else skipped++;
  }
  const names = Object.keys(groups);
  if (!used) { $('#msg').textContent = 'No reply in this file matches a pack question. Check the formats in step 2.'; return; }
  for (const n of names) { yours = yours.filter(y => y.name !== n + ' (yours)'); yours.push({id: 'yours:' + n, name: n + ' (yours)', kind: 'your file, not saved', yours: true, replies: groups[n]}); }
  open = 'yours:' + names[0]; board();
  $('#msg').textContent = `Scored ${used} answers from ${names.length} model${names.length > 1 ? 's' : ''}${skipped ? `; skipped ${skipped} line(s) that match no question` : ''}. Your report card is open above.`;
  $('#cardslot').scrollIntoView({behavior: 'smooth', block: 'start'});
}
(async () => {
  D = await (await fetch('data.json')).json();
  T = Object.fromEntries(D.tasks.map(t => [t.task_id, t]));
  for (const im of D.images) for (const id of im.tasks) { T[id].img = im.key; IMG[im.key] = im.set; }
  board();
  document.querySelectorAll('.views button').forEach(b => b.onclick = () => { view = b.dataset.view;
    document.querySelectorAll('.views button').forEach(x => x.setAttribute('aria-pressed', x === b)); board(); });
  const drop = $('#drop'), read = f => f.text().then(t => ingest(t, f.name.replace(/\.[^.]+$/, '')));
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); }; drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); if (e.dataTransfer.files[0]) read(e.dataTransfer.files[0]); };
  $('#file').onchange = e => e.target.files[0] && read(e.target.files[0]);
  $('#sample').onclick = async () => ingest(await (await fetch('sample_replies.jsonl')).text(), 'Sample: Gemini 3.1 Flash-Lite replies');
})();
</script></body></html>
"""

if __name__ == "__main__":
    main()
