"""Build a self-contained demo page for judges.

Sections: the results in one table, "How a task is made" (one real scene through every pipeline step,
from pipeline_visuals.py), and a browser of tasks: image -> question -> each model's real reply ->
automatic ✓/✗ -> answer-key reveal, with counterfactual pairs.

Usage:
  python3 pipeline_visuals.py --scene level4_seed48947 --out docs/pipeline
  python3 build_demo.py --dataset dataset --run results/models --baselines results/offline_baselines \
      --pipeline docs/pipeline --out docs/demo
Open docs/demo/index.html in a browser (no server needed). --fragment writes the page body only
(for hosts that add their own <html>/<head>/<body>).
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
from thirstmap.scoring import score

BASELINES = {"mock:oracle": "baseline: answer key", "mock:random": "baseline: random guess"}
SIZE = {"Qwen2.5-VL-3B": "3B", "Qwen2-VL-2B": "2B", "SmolVLM2-2.2B": "2.2B", "SmolVLM-256M": "0.26B"}
E = html.escape


def display(model):
    """'hf:Qwen/Qwen2.5-VL-3B-Instruct' -> 'Qwen2.5-VL-3B'; 'openai:gemini-3.5-flash-lite' -> 'Gemini 3.5 Flash-Lite'."""
    name = model.split(":", 1)[-1].split("/")[-1].split("@")[0]
    if name.startswith("gemini-"):
        v = name.split("-")
        return "Gemini " + v[1] + " " + "-".join(x.title() for x in v[2:])
    return name.replace("-Instruct", "")


def pairs_all(m):
    """Before-and-after pairs over the frontier set and its pair extension: (both halves right, pairs)."""
    k = n = 0
    for run in ("results/frontier", "results/frontier_pairs"):
        f = Path(run) / "summary.json"
        if f.exists():
            v = json.loads(f.read_text()).get("counterfactual_pairs", {}).get(m, {})
            k += round(v.get("pair_accuracy", 0) * v.get("pairs", 0))
            n += v.get("pairs", 0)
    return k, n


def hero_html(out):
    """The top of the page: what it is, three actions, key facts, and the findings in four cards (from the files)."""
    F = json.loads(Path("results/frontier/summary.json").read_text())
    man = json.loads(Path("eval_set/manifest_full_dataset.json").read_text())
    errata = sum(1 for _ in open("dataset/errata.jsonl")) if Path("dataset/errata.jsonl").exists() else 0
    vc = F["vs_chance"]
    best = max(vc, key=lambda m: vc[m]["correct"] / vc[m]["n"])
    acc = lambda m: vc[m]["correct"] / vc[m]["n"]
    lite = sorted((m for m in vc if "flash-lite" in m and F["overall"][m].get("blind") is not None), key=acc, reverse=True)
    opens = [m for m in vc if m.startswith("hf:")]
    bk, bn = pairs_all(best)
    others = [pairs_all(m)[0] for m in vc if m != best]
    fig = next(iter(sorted((out / "analysis").glob("pair__*Q8__thermal*")) + sorted((out / "analysis").glob("pair__*.jpg"))), None)
    cards = [(pct(acc(best)), f"{E(display(best))}, the best model, on {vc[best]['n']} shared questions. Guessing scores {pct(vc[best]['chance'])}.", "")]
    if lite:
        m = lite[0]
        cards.append((f"{pct(acc(m))} → {pct(F['overall'][m]['blind'])}", f"{E(display(m))} with the image, then without it: back to "
                      "guessing. The questions need the picture.", ""))
    cards.append((f"{bk} of {bn}", "before-and-after pairs the best model gets right on both halves"
                  + ("; every other model, none." if not any(others) else f"; the others at most {max(others)}."), "warn"))
    if opens:
        cards.append((f"{pct(min(map(acc, opens)))}–{pct(max(map(acc, opens)))}", "Open models up to 3B parameters: at or below "
                      "guessing on the same questions.", ""))
    figure = (f'<figure class="hero-fig"><img src="analysis/{E(fig.name)}" alt="Gemini 3.5 Flash answers drawn on a thermal scene '
              'and its twin: right on the original, the same answer after the water was cooled" width="1304" height="840">'
              '<figcaption>The best model, right on the scene (left) and wrong on its twin (right): the water was cooled, '
              'the answer did not change.</figcaption></figure>') if fig else ""
    facts = [(f"{man['n_tasks'] - errata:,}", "verified tasks"), (f"{man['counterfactual_pairs']['pairs']}", "before-and-after twins"),
             (f"{len(man['tasks_by_skill'])}", "reasoning skills"), (f"{len([k for k in man['tasks_by_terrain'] if k != 'synthetic'])}", "real Indian cities")]
    hero = f"""<header class="hero" id="top"><div class="wrap hero-in"><div class="hero-text">
<span class="eyebrow">Innodata AI Hackathon 2026 · Track 2: Visual Task Factory</span>
<h1>Can AI trace water through the landscape?</h1>
<p class="lede big">AI is drinking India's water. ThirstMap generates landscapes, simulates where their water flows, and asks
AI where a data centre's wastewater goes. The code builds the land, so it already knows every answer.</p>
<div class="ctas"><a class="btn primary" href="https://yugesh1111.github.io/THIRSTMAP/film.html">▶ Watch the 4-minute film</a>
<a class="btn" href="#try">Try it yourself</a><a class="btn" href="https://yugesh1111.github.io/THIRSTMAP/leaderboard/">Score your model</a></div>
<ul class="facts">{''.join(f'<li><b>{a}</b> {b}</li>' for a, b in facts)}</ul></div>{figure}</div></header>
<section id="found"><div class="wrap"><h2>What we found</h2>
<div class="finds">{''.join(f'<div class="find {c}"><b>{a}</b><p>{t}</p></div>' for a, t, c in cards)}</div>
<p class="more">Go deeper: <a href="https://github.com/yugesh1111/THIRSTMAP/blob/main/docs/ThirstMap_summary.pdf">one-page summary (PDF)</a> ·
<a href="https://github.com/yugesh1111/THIRSTMAP/blob/main/docs/FAQ.md">tough questions, answered</a> ·
<a href="https://yugesh1111.github.io/THIRSTMAP/human/">take the human test</a> ·
<a href="https://colab.research.google.com/github/yugesh1111/THIRSTMAP/blob/main/ThirstMap_quickstart.ipynb">run it in Colab</a> ·
<a href="https://yugesh1111.github.io/THIRSTMAP/thirstmap_demo.mp4">90-second walkthrough</a></p></div></section>"""
    return hero


def pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def fmt(v):
    if isinstance(v, list):
        return ", ".join(map(str, v)) if v else "none"
    return "–" if v is None else str(v)


def results_html(run, finetune):
    S = json.loads((run / "summary.json").read_text())
    rows = []
    for m in S["models"]:
        vc = S["vs_chance"].get(m)
        if not vc or not m.startswith("hf:"):
            continue
        probes = list(S.get("perception_probes", {}).get(m, {}).values())
        read = sum(v["acc"] * v["n"] for v in probes) / sum(v["n"] for v in probes) if probes else None
        rows.append(dict(name=display(m), acc=vc["correct"] / vc["n"], k=vc["correct"], n=vc["n"], chance=vc["chance"],
                         p=vc["p_value"], blind=S["overall"][m]["blind"],
                         pair=S["counterfactual_pairs"].get(m, {}).get("pair_accuracy"), read=read))
    rows.sort(key=lambda r: -r["acc"])
    top = max(0.25, max(r["acc"] for r in rows) * 1.25)
    body = []
    for r in rows:
        w, c = 100 * r["acc"] / top, 100 * r["chance"] / top
        body.append(
            f'<tr><th scope="row">{E(r["name"])} <span class="muted">{SIZE.get(r["name"], "")}</span></th>'
            f'<td><div class="acc"><span class="num">{pct(r["acc"])}</span>'
            f'<span class="bar" title="{pct(r["acc"])} correct; random guessing: {pct(r["chance"])}">'
            f'<i style="width:{w:.1f}%"></i><b style="left:{c:.1f}%"></b></span></div></td>'
            f'<td class="num">{pct(r["blind"])}</td><td class="num">{r["p"]:.2f}</td>'
            f'<td class="num">{pct(r["pair"])}</td><td class="num">{pct(r["read"])}</td></tr>')
    chance = rows[0]["chance"] if rows else None
    ft = ""
    fs = finetune / "summary.json" if finetune else None
    if fs and fs.exists():
        F = json.loads(fs.read_text())
        base = next((m for m in F["models"] if "(base)" in m), None)
        tuned = next((m for m in F["models"] if "fine-tuned" in m), None)
        if base and tuned:
            vb, vt = F["vs_chance"][base], F["vs_chance"][tuned]
            ft = (f'<p class="note"><b>Fine-tuning.</b> SmolVLM-256M trained on 300 ThirstMap tasks went from '
                  f'{pct(vb["correct"] / vb["n"])} to {pct(vt["correct"] / vt["n"])} on {vt["n"]} questions from '
                  f'scenes it never saw, and now scores {pct(vt["correct"] / vt["n"])} with the image against '
                  f'{pct(F["overall"][tuned]["blind"])} without it. The dataset can teach the skill, a little.</p>')
    def pair_note(F):
        cp = {m: v for m, v in F.get("counterfactual_pairs", {}).items() if v.get("pairs")}
        if not cp:
            return ""
        top_m, top = max(cp.items(), key=lambda kv: kv[1]["pair_accuracy"])
        if top["pair_accuracy"] == 0:
            return "Gemini answers far more questions correctly, yet no model got both the original and its changed twin right."
        k = round(top["pair_accuracy"] * top["pairs"])
        return (f"The best model, {E(display(top_m))}, got both the original and its changed twin right in only {k} of "
                f"{top['pairs']} pairs; every other model got none.")
    fr = ""
    fs2 = Path("results/frontier/summary.json")
    if fs2.exists():
        F = json.loads(fs2.read_text())
        frows = []
        for m in F["models"]:
            vc = F["vs_chance"].get(m)
            if vc:
                pk, pn = pairs_all(m)
                acc, ch = vc["correct"] / vc["n"], vc["chance"]
                top_f = 1.0
                frows.append((acc, f'<tr><th scope="row">{E(display(m))} <span class="muted">{"open" if m.startswith("hf:") else "API"}</span></th>'
                              f'<td><div class="acc"><span class="num">{pct(acc)}</span><span class="bar" title="{pct(acc)} correct; '
                              f'random guessing: {pct(ch)}"><i style="width:{100 * acc / top_f:.1f}%"></i><b style="left:{100 * ch / top_f:.1f}%"></b></span>'
                              f'<span class="muted num">{vc["correct"]}/{vc["n"]}</span></div></td>'
                              f'<td class="num">{pct(F["overall"].get(m, {}).get("blind"))}</td><td class="num">{vc["p_value"]:.1g}</td>'
                              f'<td class="num"><b class="{"bad" if pk == 0 else ""}">{pk} of {pn}</b></td></tr>'))
        if frows:
            fr = (f'<h3>Frontier check: Gemini vs open models on the same {F.get("compared_on_tasks", "")} questions</h3>'
                  '<div class="table"><table><thead><tr><th scope="col">Model</th><th scope="col">Correct, with the image '
                  f'<span class="key"><i></i>chance {pct(next(iter(F["vs_chance"].values()))["chance"])}</span></th>'
                  '<th scope="col">Without the image</th><th scope="col">p vs guessing</th>'
                  '<th scope="col">Pairs right, both halves</th></tr></thead><tbody>'
                  + "".join(r for _, r in sorted(frows, key=lambda x: -x[0])) + '</tbody></table></div>'
                  '<p class="note">A free Gemini key allows 20 requests per model per day, so every question about an image '
                  'went in one request, identically for every model. Pairs count every before-and-after pair the model '
                  'answered, in the frontier set and its pair extension on new scenes. Pick “Frontier check” in the '
                  'task browser to see every reply, or open the <a href="https://yugesh1111.github.io/THIRSTMAP/leaderboard/">'
                  'leaderboard</a> for each model\'s report card.</p>')
    tc = ""
    if Path("docs/trap_chart.png").exists():
        tc = ('<figure class="pairfig"><img src="trap_chart.png" alt="How often each model fell for a built-in trap, '
              'and which traps" loading="lazy" width="2210" height="884"><figcaption>Gemini falls for the built-in '
              'traps far less often than the open models, but still does.</figcaption></figure>')
    return fr + f"""<h3>Open models, main run: {rows[0]["n"] if rows else 0} questions each, one per request</h3><div class="table"><table>
<thead><tr><th scope="col">Model</th><th scope="col">Correct, with the image <span class="key"><i></i>chance {pct(chance)}</span></th>
<th scope="col">Without the image</th><th scope="col">p vs guessing</th><th scope="col">Both halves of a pair right</th>
<th scope="col">Reads the labels</th></tr></thead>
<tbody>{''.join(body)}</tbody></table></div>
<p class="note">{rows[0]["n"] if rows else 0} questions per model, the same for every model, plus 30 before-and-after pairs and
16 reading checks. Free open-weight models from Hugging Face, run locally with greedy decoding. Every reply on this
page is the model's real, unedited output.</p>{ft}{tc}"""


def pipeline_html(pdir, tasks, run):
    f = json.loads((pdir / "steps.json").read_text())
    scene = f["scene"]
    q1 = next((t for t in tasks.values() if t["scene_id"] == scene and t["qid"] == "Q1" and t["style"] == "satellite"),
              None)
    cf = next((t for t in tasks.values() if q1 and t.get("pair_id") == q1.get("pair_id")
               and t.get("variant") == "counterfactual"), None)
    replies = defaultdict(dict)
    for line in open(run / "responses.jsonl"):
        r = json.loads(line)
        if r["mode"] == "image" and r["task_id"] in {q1 and q1["task_id"], cf and cf["task_id"]}:
            replies[r["task_id"]][display(r["model"])] = score(tasks[r["task_id"]], r["raw"]) | {"raw": r["raw"]}
    why_txt = {"close, other stream": "is close to the data centre but on another stream",
               "upstream, same stream": "is on the same stream but upstream of O"}
    traps = "; ".join(f"{v} {why_txt.get(why, why)}" for v, why in f["traps"].items())
    km = f"{f['size_km']:.0f}"

    def fig(src, alt, cap=None):
        c = f"<figcaption>{E(cap)}</figcaption>" if cap else ""
        return f'<figure><img src="pipeline/{src}" alt="{E(alt)}" loading="lazy" width="640" height="640">{c}</figure>'

    def reply_rows(task):
        out = []
        for name, sc in sorted(replies.get(task["task_id"], {}).items()):
            tags = f' <span class="tag">{E(", ".join(sc["tags"]))}</span>' if sc["tags"] else ""
            out.append(f'<li><span class="mark {"ok" if sc["correct"] else "bad"}" aria-label="'
                       f'{"right" if sc["correct"] else "wrong"}">{"✓" if sc["correct"] else "✗"}</span>'
                       f'<span><b>{E(name)}</b> answered {E(fmt(sc["parsed"]))}{tags}</span></li>')
        return "".join(out)

    steps = [
        ("Terrain", f"Fractal terrain for a {km} × {km} km area on a {f['cells']} × {f['cells']} grid of "
         f"{f['cell_m']} m cells. Elevation runs from {f['elev_min_m']} m (light) to {f['elev_max_m']} m (dark), "
         "higher in the north, so streams drain south.", fig("1_terrain.png", "Shaded elevation of the scene")),
        ("Water simulation", "Hollows are filled first (priority-flood), then every cell sends its water to its "
         "steepest downhill neighbour (D8 routing). Counting the cells upstream of each point draws the streams: "
         f"{f['stream_cells']:,} stream cells, {f['lake_cells']} cells of ponded water, and up to "
         f"{f['max_upstream_km2']} km² draining through one point.", fig("2_water.png", "Flow accumulation map")),
        ("Scene script", f"The script places data centre DC-1 and its outfall O, {len(f['villages'])} villages, "
         f"{len(f['wetlands'])} candidate wetlands and a water intake I. Traps are built in: {traps} "
         "(yellow). A model that answers by distance instead of by flow picks it.",
         fig("3_scene.png", "Placements: data centre, outfall, villages, wetlands")),
        ("Answer key", f"Tracing downhill from O gives the reference answer. The question: “{E(f['question'])}” "
         f"The answer: <b>{E(fmt(f['answer']))}</b>. No model and no person is involved.",
         fig("4_answer.png", "Wastewater path from O to the villages it reaches")),
        ("Independent check", f"pysheds, a separate hydrology library, recomputes the flow. It agrees on "
         f"{f['pysheds_agree_pct']}% of cells (red: the {f['pysheds_disagree_cells']} cells that differ), traces "
         f"the same path (blue under orange) and gives the same answer to {f['answers_identical']} questions. "
         "A question whose answers disagree is dropped, never edited.",
         fig("5_check.png", "Cells where the two flow computations agree")),
        ("Three image styles", "The scene is rendered as a satellite-style image, a topographic map and a thermal "
         "image. One answer key serves all three, and each question is asked only in the styles that show its "
         "evidence.",
         '<div class="trio">' + fig("6_satellite.jpg", "Satellite-style image", "Satellite-style")
         + fig("6_map.jpg", "Topographic map", "Topographic map")
         + fig("6_thermal.jpg", "Thermal image", "Thermal, °C above normal") + "</div>"),
        ("Pixel evidence", f"Before release, the answer path is checked in the image the model will see. Each dot is "
         f"a path cell; green means water is visible there ({f['pixel_visible_pct']:.0f}% of {f['pixel_cells']} "
         "cells). Labels must not overlap or leave the frame. Rebuilt from its seed, this image is "
         f"{'pixel-identical to' if f.get('satellite_rebuilt_identical') else 'different from'} the dataset copy.",
         fig("7_pixels.jpg", "Answer path cells checked on the satellite image")),
        ("Before-and-after twin", f"The twin changes one thing: {E(f.get('twin_change') or '')}. Only "
         f"{f.get('twin_pixels_changed_pct')}% of pixels change (outlined in pink). The correct answer moves from "
         f"<b>{E(fmt(f['answer']))}</b> to <b>{E(fmt(f.get('twin_answer')))}</b>, so only a model that looks can be "
         "right on both.",
         '<div class="duo">' + fig("8_original.jpg", "Original scene", f"Original: {fmt(f['answer'])}")
         + fig("8_twin.jpg", "Twin with the moved outfall outlined", f"Twin: {fmt(f.get('twin_answer'))}")
         + "</div>"),
    ]
    if q1 and cf:
        steps.append(("Scoring", "Each reply is parsed and compared with the key automatically. Wrong answers are "
                      "tagged with the trap they fell for. These are the real replies of the four open models to this "
                      "scene and its twin:",
                      f'<div class="scores"><div><h4>Original · key {E(fmt(q1["answer"]))}</h4><ul class="replies">'
                      f'{reply_rows(q1)}</ul></div><div><h4>Twin · key {E(fmt(cf["answer"]))}</h4>'
                      f'<ul class="replies">{reply_rows(cf)}</ul></div></div>'))
    out = []
    for k, (title, text, visual) in enumerate(steps, 1):
        out.append(f'<li class="step"><div class="text"><span class="n">{k}</span><h3>{E(title)}</h3>'
                   f'<p>{text}</p></div><div class="visual">{visual}</div></li>')
    return f'<ol class="steps">{"".join(out)}</ol>', scene


def try_section(fdir, tasks, root, out, n_single=4):
    """'Try it yourself': a few frontier questions that are NOT in the human test, scored in the browser."""
    best, acc = None, defaultdict(list)
    rows = {}
    for line in open(fdir / "responses.jsonl"):
        r = json.loads(line)
        if r["mode"] == "image" and r["task_id"] in tasks and not r.get("error") and not r["model"].startswith("hf:"):
            sc = score(tasks[r["task_id"]], r["raw"])
            rows[(r["model"], r["task_id"])] = sc
            acc[r["model"]].append(sc["correct"])
    if not acc:
        return "", []
    best = max(acc, key=lambda m: sum(acc[m]) / len(acc[m]))
    held = set()
    hp = Path("human_eval/index.html")
    if hp.exists():                                    # keep the human test's questions unseen
        import re as _re
        m_ = _re.search(r'<script id="data" type="application/json">(.*?)</script>', hp.read_text(), _re.S)
        if m_:
            held = {d["id"] for d in json.loads(html.unescape(m_.group(1)))}
    pool = [tasks[t] for (m, t) in rows if m == best and t not in held]
    pick = []
    # one before-and-after pair the best model got right on one side only
    for t in sorted(pool, key=lambda t: t["task_id"]):
        if t.get("variant") == "base" and t.get("pair_id"):
            twin = t["pair_id"].replace("__", "_cf__", 1)
            if twin in tasks and (best, twin) in rows and twin not in held and \
                    rows[(best, t["task_id"])]["correct"] != rows[(best, twin)]["correct"]:
                pick = [t, tasks[twin]]
                break
    target = len(pick) + n_single + (0 if pick else 2)
    for distinct_scene in (True, False):          # different skills, preferably from different scenes and styles
        seen = {t["skill"] for t in pick}
        scenes = {t["scene_id"].removesuffix("_cf") for t in pick}
        styles = defaultdict(int)
        for t in pick:
            styles[t["style"]] += 1
        for t in sorted(pool, key=lambda t: (styles[t["style"]], t["level"], t["task_id"])):
            if len(pick) >= target:
                break
            if t["skill"] in seen or t.get("pair_id") or t["qid"] == "Q4":
                continue
            if distinct_scene and t["scene_id"].removesuffix("_cf") in scenes:
                continue
            pick.append(t); seen.add(t["skill"]); scenes.add(t["scene_id"].removesuffix("_cf")); styles[t["style"]] += 1
    data = []
    for t in pick:
        names = {}
        for key in ("image", "reveal"):
            src = root / t[key]
            name = src.parent.name + "_" + src.stem + ".jpg"
            if not (out / "img" / name).exists():
                Image.open(src).convert("RGB").save(out / "img" / name, quality=85)
            names[key] = "img/" + name
        g = rows[(best, t["task_id"])]
        data.append(dict(id=t["task_id"], image=names["image"], reveal=names["reveal"], q=t["question"],
                         ctx=t["prompt"].split("Question:")[0].strip(), scoring=t["scoring"], options=t["options"],
                         answer=t["answer"], tol=t.get("tolerance"), unit="m" if t["qid"] == "Q10" else "°C",
                         skill=SKILL_LABEL[t["skill"]], variant=t.get("variant"), change=t.get("cf_change"),
                         model=display(best), model_answer=g["parsed"], model_right=g["correct"]))
    if not data:
        return "", []
    section = (f'<section id="try"><div class="wrap"><h2>Try it yourself</h2>'
               f'<p class="lede">Answer {len(data)} questions the way the models did, then check: the page scores you '
               f'with the same rules as the models and shows what {E(display(best))} answered. '
               'These questions are not in the human test.</p>'
               '<p class="stats" id="tally" aria-live="polite"></p><div id="trylist"></div></div></section>')
    return section, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--run", required=True)
    ap.add_argument("--per-skill", type=int, default=6)
    ap.add_argument("--pairs", type=int, default=8, help="counterfactual pairs to include")
    ap.add_argument("--out", default="demo")
    ap.add_argument("--baselines", default=None,
                    help="run with offline baselines (mock:oracle / mock:random) to show beside the models")
    ap.add_argument("--finetune", default="results/finetune")
    ap.add_argument("--pipeline", default=None, help="folder from pipeline_visuals.py")
    ap.add_argument("--frontier", default=None, help="results folder from frontier.py (batched protocol)")
    ap.add_argument("--analysis", default=None, help="folder from overlays.py (answer overlays, pairs, stories)")
    ap.add_argument("--fragment", action="store_true", help="write the page body only, without <html>/<head>/<body>")
    a = ap.parse_args()
    ds, run, out = Path(a.dataset), Path(a.run), Path(a.out)
    root = ds.resolve()
    from thirstmap import errata
    bad = errata.load(ds)                    # audited-out tasks are never shown (docs/AUDIT.md)
    tasks = {}
    for line in open(ds / "tasks.jsonl"):
        t = json.loads(line)
        if t["task_id"] not in bad:
            tasks[t["task_id"]] = t
    answers = defaultdict(dict)
    for line in open(run / "responses.jsonl"):
        r = json.loads(line)
        if not r.get("error") and r["mode"] == "image" and r["task_id"] in tasks:
            sc = score(tasks[r["task_id"]], r.get("raw", ""))       # re-score the raw reply, as the report does
            answers[r["task_id"]][display(r["model"])] = dict(raw=r.get("raw", "")[:400], parsed=sc["parsed"],
                                                              correct=sc["correct"], tags=sc["tags"])
    count = defaultdict(int)                               # leave out models whose run is still incomplete
    for v in answers.values():
        for m in v:
            count[m] += 1
    keep = {m for m, c in count.items() if c >= 0.8 * max(count.values())}
    answers = {tid: {m: x for m, x in v.items() if m in keep} for tid, v in answers.items()}
    most = max(len(v) for v in answers.values())          # only tasks that every model answered
    answers = {tid: v for tid, v in answers.items() if len(v) == most}
    if a.baselines:
        for line in open(Path(a.baselines) / "responses.jsonl"):
            r = json.loads(line)
            if r["mode"] == "image" and r["task_id"] in answers and r["model"] in BASELINES:
                sc = score(tasks[r["task_id"]], r.get("raw", ""))
                answers[r["task_id"]][BASELINES[r["model"]]] = dict(raw="", parsed=sc["parsed"], correct=sc["correct"],
                                                                    tags=sc["tags"], baseline=True)
    by_skill = defaultdict(list)
    for tid in answers:
        by_skill[tasks[tid]["skill"]].append(tid)
    rng = random.Random(0)
    chosen = []
    for sk in SKILL_ORDER:
        pool = sorted(by_skill.get(sk, []))
        rng.shuffle(pool)
        chosen += sorted([t for t in pool if not tasks[t].get("pair_id")][: a.per_skill],
                         key=lambda t: tasks[t]["level"])
    pair_ids = sorted({tasks[t]["pair_id"] for t in answers if tasks[t].get("pair_id")})
    rng.shuffle(pair_ids)
    by_pair = defaultdict(dict)
    for tid in answers:
        if tasks[tid].get("pair_id"):
            by_pair[tasks[tid]["pair_id"]][tasks[tid]["variant"]] = tid
    kinds_seen = defaultdict(int)
    for pid in pair_ids:
        v = by_pair[pid]
        kind = tasks[v.get("counterfactual", "")]["cf_kind"] if "counterfactual" in v else None
        if len(v) == 2 and kinds_seen[kind] < max(1, a.pairs // 3):
            kinds_seen[kind] += 1
            chosen += [v["base"], v["counterfactual"]]

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
                          pair=t.get("pair_id"), variant=t.get("variant"), change=t.get("cf_change"),
                          question=t["question"], answer=t["answer"], image=names["image"],
                          reveal=names["reveal"], models=answers[tid]))
    fdir = Path(a.frontier) if a.frontier else None
    if fdir and (fdir / "responses.jsonl").exists():
        fans = defaultdict(dict)
        for line in open(fdir / "responses.jsonl"):
            r = json.loads(line)
            if r["task_id"] in tasks and not r.get("error"):
                sc = score(tasks[r["task_id"]], r.get("raw", ""))
                fans[r["task_id"]][display(r["model"])] = dict(raw=r.get("raw", "")[:200], parsed=sc["parsed"],
                                                               correct=sc["correct"], tags=sc["tags"])
        most = max(len(v) for v in fans.values())
        order = {i["image"]: k for k, i in enumerate(json.loads((fdir / "set.json").read_text())["images"])}
        for tid in sorted((t for t, v in fans.items() if len(v) == most),
                          key=lambda t: (order.get(f"{tasks[t]['scene_id']}__{tasks[t]['style']}", 99), tasks[t]["qid"])):
            t = tasks[tid]
            names = {}
            for key in ("image", "reveal"):
                src = root / t[key]
                name = src.parent.name + "_" + src.stem + ".jpg"
                if not (out / "img" / name).exists():
                    Image.open(src).convert("RGB").save(out / "img" / name, quality=85)
                names[key] = "img/" + name
            items.append(dict(id=tid, skill=SKILL_LABEL[t["skill"]], style=t["style"], level=t["level"],
                              pair=t.get("pair_id"), variant=t.get("variant"), change=t.get("cf_change"),
                              question=t["question"], answer=t["answer"], image=names["image"],
                              reveal=names["reveal"], models=fans[tid], frontier=True))
    show = ""
    adir = Path(a.analysis) if a.analysis else None
    if adir and (adir / "analysis.json").exists():
        A = json.loads((adir / "analysis.json").read_text())
        best = A.get("best_api")
        (out / "analysis").mkdir(exist_ok=True)
        stories = defaultdict(list)
        for st in A["stories"]:
            if st["model"] == best:
                stories[st["task_id"]].append(st["text"])
        for it in items:
            if it.get("frontier"):
                ov = A["overlays"].get(it["id"], {}).get(best)
                if ov and (adir / ov).exists():
                    shutil.copy(adir / ov, out / "analysis" / Path(ov).name)
                    it["overlay"] = "analysis/" + Path(ov).name
                    it["overlay_by"] = display(best)
                it["stories"] = stories.get(it["id"], [])
        picks = [x for x in A["pairs"] if x["model"] == best and x["original_right"] != x["twin_right"]]
        picks += [x for x in A["pairs"] if x["model"] == best and x not in picks]
        cards, seen = [], set()
        for x in picks:
            if x["qid"] in seen or len(cards) >= 3 or not (adir / x["file"]).exists():
                continue
            seen.add(x["qid"])
            shutil.copy(adir / x["file"], out / "analysis" / ("pair__" + Path(x["file"]).name))
            twin_story = [st["text"] for st in A["stories"] if st["model"] == best
                          and st["task_id"] == x["pair_id"].replace("__", "_cf__", 1)]
            verdict = (f"Right on the original, wrong on the twin{' with the same answer' if x['same_answer'] else ''}."
                       if x["original_right"] and not x["twin_right"] else
                       "Wrong on the original, right on the twin." if x["twin_right"] and not x["original_right"]
                       else "Wrong on both.")
            cards.append(f'<figure class="pairfig"><img src="analysis/pair__{E(Path(x["file"]).name)}" alt="{E(display(best))} answers '
                         f'on a scene and its twin, drawn on the images" loading="lazy" width="1304" height="840">'
                         f'<figcaption><b>{E(x["question"])}</b> {E(verdict)} Original key {E(fmt(x["original"]["answer"]))}, '
                         f'model said {E(fmt(x["original"]["model"]))}; twin key {E(fmt(x["twin"]["answer"]))}, '
                         f'model said {E(fmt(x["twin"]["model"]))}.'
                         + (f' <span class="story">On the ground: {E(" ".join(twin_story[:2]))}</span>' if twin_story else "")
                         + '</figcaption></figure>')
        if cards:
            show = ('<section id="where"><div class="wrap"><h2>Where the models sent the water</h2>'
                    f'<p class="lede">The best frontier model’s answers ({E(display(best))}) drawn on the exact images it saw, '
                    'for a scene and its twin. Blue is the true water path; green, red and amber mark right, wrong and '
                    'missed answers.</p>' + "".join(cards) + '</div></section>')
    if Path("docs/trap_chart.png").exists():
        shutil.copy("docs/trap_chart.png", out / "trap_chart.png")
    try_html, try_data = "", []
    if fdir and (fdir / "responses.jsonl").exists():
        try_html, try_data = try_section(fdir, tasks, root, out)
    pipe = ""
    if a.pipeline:
        shutil.copytree(a.pipeline, out / "pipeline", ignore=shutil.ignore_patterns("*.json"))
        steps, scene = pipeline_html(Path(a.pipeline), tasks, run)
        pipe = (f'<section class="band" id="how"><div class="wrap"><h2>How a task is made</h2>'
                f'<p class="lede">One real scene from the dataset (<code>{E(scene)}</code>), followed through every '
                f'step of the pipeline.</p>{steps}</div></section>')
    page = (HEAD + BODY.replace("__HERO__", hero_html(out) if Path("results/frontier/summary.json").exists() else "")
            .replace("__RESULTS__", results_html(run, Path(a.finetune) if a.finetune else None))
            .replace("__PIPELINE__", pipe + try_html + show)
            .replace("__TRY__", json.dumps(try_data, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__DATA__", json.dumps(items, ensure_ascii=False).replace("</", "<\\/")))
    page += SPY
    if not a.fragment:
        page = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
                + page.replace("</style>", "</style></head><body>", 1) + "</body></html>\n")
    (out / "index.html").write_text(page)
    print(f"demo with {len(items)} tasks{' + pipeline walkthrough' if pipe else ''} -> {out / 'index.html'}")


SPY = """<script>
(() => {               // the nav bar marks the section you are reading
  const links = [...document.querySelectorAll('.anchors a')];
  if (!('IntersectionObserver' in window) || !links.length) return;
  const obs = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting)
    links.forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id)); }), {rootMargin: '-40% 0px -55% 0px'});
  links.forEach(a => { const t = document.querySelector(a.getAttribute('href')); if (t) obs.observe(t); });
})();
</script>
"""

HEAD = r"""<title>ThirstMap demo</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&family=Space+Grotesk:wght@500;600;700&display=swap">
<style>
/* Layout: one reading column; results first, then the pipeline as numbered steps (text beside its picture), then the task browser. */
:root{
  --bg:#f3f6f7; --surface:#ffffff; --ink:#0f1417; --ink2:#4b5860; --line:#d9e1e5;
  --water:#2a78d6; --waste:#d95926; --ok:#0b7a0b; --bad:#c13a3a; --chip:#eaf0f3;
  --display:"Space Grotesk",ui-sans-serif,system-ui,sans-serif;
  --text:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0e1316; --surface:#161c20; --ink:#eef2f4; --ink2:#a7b3ba; --line:#2a343a;
  --water:#3987e5; --waste:#e2703f; --ok:#34b334; --bad:#e66767; --chip:#1f272c; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0e1316; --surface:#161c20; --ink:#eef2f4; --ink2:#a7b3ba; --line:#2a343a;
  --water:#3987e5; --waste:#e2703f; --ok:#34b334; --bad:#e66767; --chip:#1f272c; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--text)}
.wrap{max-width:1120px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
h1,h2,h3,h4{font-family:var(--display);text-wrap:balance;margin:0;line-height:1.2}
h1{font-size:clamp(26px,4vw,38px);font-weight:700}
h2{font-size:24px;font-weight:600}
h3{font-size:18px;font-weight:600}
h4{font-size:14px;font-weight:600}
p{margin:0}
code{font-family:var(--mono);font-size:.88em}
.muted,.note{color:var(--ink2)}
.note{font-size:14px;max-width:75ch}
header{padding-block:28px 8px}
header .wrap{display:grid;gap:10px}
.links{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:14px}
.links a{color:var(--water);font-weight:500;text-underline-offset:3px}
.eyebrow{font:600 12px/1 var(--text);letter-spacing:.08em;text-transform:uppercase;color:var(--water)}
.lede{color:var(--ink2);max-width:70ch}
section{padding-block:22px}
section .wrap{display:grid;gap:14px}
.band{background:var(--surface);border-block:1px solid var(--line)}
.table{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;min-width:640px;font-size:14px}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
thead th{font-weight:500;color:var(--ink2);font-size:13px}
tbody th{font-weight:600;white-space:nowrap}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.acc{display:flex;align-items:center;gap:10px;min-width:170px}
.acc .num{width:3.2em;font-weight:600}
.bar{position:relative;flex:1;height:8px;background:var(--chip);border-radius:4px}
.bar i{position:absolute;inset:0 auto 0 0;background:var(--water);border-radius:4px}
.bar b{position:absolute;top:-5px;bottom:-5px;width:2px;background:var(--ink);margin-left:-1px}
.key{display:inline-flex;align-items:center;gap:6px;margin-left:8px;font-size:12px}
.key i{display:inline-block;width:2px;height:12px;background:var(--ink)}
.steps{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:28px}
.step{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px;align-items:start;padding-top:22px;border-top:1px solid var(--line)}
.visual>figure{max-width:520px}
.step:first-child{border-top:0;padding-top:0}
.step .text{display:grid;gap:8px;align-content:start}
.step .n{font:700 13px/1 var(--display);color:var(--water);letter-spacing:.04em}
.step p{color:var(--ink2);max-width:60ch}
.step p b{color:var(--ink)}
figure{margin:0;display:grid;gap:6px;min-width:0}
figure img{width:100%;height:auto;display:block;border-radius:8px;border:1px solid var(--line);background:var(--bg)}
figcaption{font-size:13px;color:var(--ink2)}
.trio{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.duo{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.scores{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.scores>div{border:1px solid var(--line);border-radius:10px;padding:12px;display:grid;gap:8px;background:var(--bg)}
.replies{list-style:none;margin:0;padding:0;display:grid;gap:6px;font-size:14px}
.replies li{display:grid;grid-template-columns:20px minmax(0,1fr);gap:6px}
.mark{font-weight:700}.ok{color:var(--ok)}.bad{color:var(--bad)}
.tag{font-size:12px;color:var(--bad)}
@media (max-width:820px){.step{grid-template-columns:1fr}.trio{grid-template-columns:1fr 1fr}.scores{grid-template-columns:1fr}}
@media (max-width:480px){.trio,.duo{grid-template-columns:1fr}}
.bar-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
select,button{font:inherit;font-size:14px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}
button{cursor:pointer}
select:focus-visible,button:focus-visible{outline:2px solid var(--water);outline-offset:2px}
.stats{margin-left:auto;color:var(--ink2);font-size:14px;font-variant-numeric:tabular-nums}
#list{display:grid;gap:16px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);overflow:hidden}
@media (max-width:820px){.card{grid-template-columns:1fr}.stats{margin-left:0;width:100%}}
.pic{position:relative;background:var(--bg)}.pic img{width:100%;height:auto;display:block}
.pic .btns{position:absolute;left:10px;bottom:10px;display:flex;flex-wrap:wrap;gap:6px}
.pic .btns button{background:var(--surface);border-color:var(--line)}
.opts{display:flex;flex-wrap:wrap;gap:8px}.opts label{border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer}
.num{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);width:9em}
#trylist{display:grid;gap:16px}
.pairfig{display:grid;gap:8px;margin:0 0 18px}.pairfig img{width:100%;height:auto;border-radius:10px;border:1px solid var(--line)}
.pairfig figcaption{font-size:14px;color:var(--ink2);max-width:90ch}.pairfig .story{display:block;margin-top:4px;color:var(--ink)}
.body{padding:16px;display:flex;flex-direction:column;gap:10px;min-width:0}
.meta{display:flex;gap:6px;flex-wrap:wrap}
.chip{font-size:12px;padding:2px 8px;border-radius:99px;background:var(--chip);color:var(--ink2)}
.q{font-weight:600}.gold{font-size:14px;color:var(--ink2)}.gold b{color:var(--ink)}
.ans{border-top:1px solid var(--line);padding-top:8px;display:grid;gap:8px}
.row{display:grid;grid-template-columns:20px minmax(0,1fr);gap:8px;align-items:start;font-size:14px}
.row small{color:var(--ink2);display:block;font-family:var(--mono);font-size:12px;overflow-wrap:anywhere}
.row.base{opacity:.65}
footer{padding-block:24px 36px;color:var(--ink2);font-size:13px}
html{scroll-behavior:smooth}section[id],header[id]{scroll-margin-top:64px}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:31;background:var(--bg)}
nav.top{position:sticky;top:env(safe-area-inset-top,0px);z-index:30;background:color-mix(in srgb,var(--bg) 90%,transparent);
  backdrop-filter:saturate(1.4) blur(10px);-webkit-backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--line)}
.nav-in{display:flex;align-items:center;gap:20px;min-height:56px}
.brand{font:700 20px var(--display);color:var(--ink);text-decoration:none;letter-spacing:-.01em}.brand span{color:var(--water)}
.anchors{display:flex;gap:18px;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0}.anchors::-webkit-scrollbar{display:none}
.anchors a,.ext a{color:var(--ink2);text-decoration:none;font-size:14px;font-weight:500;white-space:nowrap}
.anchors a:hover,.ext a:hover,.anchors a.on{color:var(--water)}.anchors a.on{text-decoration:underline;text-underline-offset:6px;text-decoration-thickness:2px}
.ext{display:flex;gap:16px;align-items:center}.ext .gh{border:1px solid var(--line);border-radius:8px;padding:5px 11px;color:var(--ink)}
@media (max-width:820px){.ext a:not(.gh){display:none}.anchors{gap:14px;-webkit-mask-image:linear-gradient(90deg,#000 80%,transparent);mask-image:linear-gradient(90deg,#000 80%,transparent);padding-right:24px}}
.hero{padding-block:44px 34px}
.hero .hero-in{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:40px;align-items:center}
.hero-text{display:grid;gap:0;align-content:start}
.hero h1{font-size:clamp(34px,4.8vw,56px);line-height:1.04;letter-spacing:-.025em;margin-top:12px}
.lede.big{font-size:17px;line-height:1.6;margin-top:16px}
.ctas{display:flex;flex-wrap:wrap;gap:10px;margin-top:24px}
.btn{display:inline-flex;align-items:center;gap:8px;font:600 15px var(--text);padding:10px 15px;border-radius:10px;border:1px solid var(--line);
  background:var(--surface);color:var(--ink);text-decoration:none;transition:border-color .15s,transform .15s}
.btn:hover{border-color:var(--water);transform:translateY(-1px)}.btn.primary{background:var(--water);border-color:var(--water);color:#fff}
.btn:focus-visible,.anchors a:focus-visible,.ext a:focus-visible,.brand:focus-visible{outline:2px solid var(--waste);outline-offset:2px}
.facts{list-style:none;padding:0;margin:24px 0 0;display:flex;flex-wrap:wrap;gap:8px}
.facts li{background:var(--chip);border-radius:99px;padding:6px 12px;font-size:13.5px;color:var(--ink2)}.facts b{color:var(--ink);font-variant-numeric:tabular-nums}
.hero-fig img{border-radius:14px;border:1px solid var(--line);box-shadow:0 20px 50px rgba(15,34,48,.16)}
.hero-fig figcaption{font-size:13.5px}
@media (max-width:900px){.hero .hero-in{grid-template-columns:1fr;gap:28px}.hero{padding-block:28px 20px}}
.finds{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.find{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px;display:grid;gap:8px;align-content:start}
.find b{font:700 32px/1.05 var(--display);font-variant-numeric:tabular-nums;letter-spacing:-.01em}.find.warn b{color:var(--bad)}
.find p{color:var(--ink2);font-size:14px}
@media (max-width:900px){.finds{grid-template-columns:1fr 1fr}}@media (max-width:520px){.finds{grid-template-columns:1fr}}
.more{font-size:14px;color:var(--ink2);max-width:none}.more a{color:var(--water)}
.acc .muted.num{width:auto;font-weight:400;font-size:13px}
h3{margin-top:10px}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
"""

BODY = r"""<nav class="top" aria-label="Sections"><div class="wrap nav-in"><a class="brand" href="#top">Thirst<span>Map</span></a>
<div class="anchors"><a href="#found">Findings</a><a href="#results">Results</a><a href="#how">How it works</a><a href="#try">Try it</a>
<a href="#where">Where models fail</a><a href="#tasks">Browse tasks</a></div>
<div class="ext"><a href="https://yugesh1111.github.io/THIRSTMAP/film.html">Film</a><a href="https://yugesh1111.github.io/THIRSTMAP/leaderboard/">Leaderboard</a>
<a class="gh" href="https://github.com/yugesh1111/THIRSTMAP">GitHub</a></div></div></nav>
__HERO__
<header class="oldhead" hidden><div class="wrap">
<span class="eyebrow">Innodata AI Hackathon · Track 2: Visual Task Factory</span>
<h1>ThirstMap: can AI trace water through the landscape?</h1>
<p class="lede">India's data centres use billions of litres of water. ThirstMap generates terrain images, simulates where
the water flows, and asks AI models where a data centre's wastewater goes. Because the code builds the landscape, it
already knows every answer.</p>
<p class="links"><a href="https://yugesh1111.github.io/THIRSTMAP/film.html">Watch the film (4 min, narrated)</a>
<a href="https://yugesh1111.github.io/THIRSTMAP/thirstmap_demo.mp4">90-second walkthrough</a>
<a href="https://github.com/yugesh1111/THIRSTMAP">Code, dataset and full results</a>
<a href="https://yugesh1111.github.io/THIRSTMAP/leaderboard/">Leaderboard: score your own model</a>
<a href="https://yugesh1111.github.io/THIRSTMAP/human/">Take the human test (32 questions, about 15 minutes)</a>
<a href="https://github.com/yugesh1111/THIRSTMAP/blob/main/docs/ThirstMap_summary.pdf">One-page summary (PDF)</a>
<a href="https://github.com/yugesh1111/THIRSTMAP/blob/main/docs/FAQ.md">Tough questions, answered</a>
<a href="https://colab.research.google.com/github/yugesh1111/THIRSTMAP/blob/main/ThirstMap_quickstart.ipynb">Run it in Colab</a></p>
</div></header>
<section id="results" class="band"><div class="wrap">
<h2>Results</h2>
__RESULTS__
</div></section>
__PIPELINE__
<section id="tasks"><div class="wrap">
<h2>Browse the tasks</h2>
<p class="lede">Each card shows the image the model saw, the question, the answer key from the simulation, and every
model's real reply, scored automatically. Grey rows are offline baselines for scale: one returns the answer key, one
guesses at random. Press “Show answer key” to see the water path.</p>
<div class="bar-row">
<select id="fs" aria-label="Skill"><option value="">All skills</option></select>
<select id="fy" aria-label="Image style"><option value="">All image styles</option><option>satellite</option><option>map</option><option>thermal</option></select>
<select id="fr" aria-label="Which tasks"><option value="">All tasks</option><option value="bad">Tasks a model got wrong</option><option value="pairs">Before-and-after pairs</option><option value="frontier">Frontier check: Gemini vs open models</option></select>
<span class="stats" id="stats"></span></div>
<div id="list"></div>
</div></section>
<footer><div class="wrap">Synthetic terrain; real-terrain scenes use Copernicus DEM GLO-30 and ESA WorldCover 2021 with
hypothetical facilities. Code, dataset and full results: github.com/yugesh1111/THIRSTMAP</div></footer>
<script id="data" type="application/json">__DATA__</script>
<script id="trydata" type="application/json">__TRY__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = v => Array.isArray(v) ? (v.length ? v.join(', ') : 'none') : (v === null || v === undefined ? '–' : String(v));
const fs = document.getElementById('fs'), fy = document.getElementById('fy'), fr = document.getElementById('fr');
[...new Set(DATA.map(d => d.skill))].forEach(s => { const o = document.createElement('option'); o.textContent = s; fs.appendChild(o); });
function render(){
  const L = document.getElementById('list'); L.textContent = '';
  let n = 0, right = 0, total = 0;
  DATA.filter(d => (!fs.value || d.skill === fs.value) && (!fy.value || d.style === fy.value)
     && (fr.value !== 'bad' || Object.values(d.models).some(m => !m.correct && !m.baseline))
     && (fr.value !== 'pairs' || d.pair) && (fr.value === 'frontier' ? d.frontier : !d.frontier)).forEach(d => {
    n++;
    const c = document.createElement('article'); c.className = 'card';
    const rows = Object.entries(d.models).map(([name, m]) => { if (!m.baseline) { total++; if (m.correct) right++; }
      return `<div class="row${m.baseline ? ' base' : ''}"><span class="mark ${m.correct ? 'ok' : 'bad'}" aria-label="${m.correct ? 'right' : 'wrong'}">${m.correct ? '✓' : '✗'}</span>
      <div><b>${esc(name)}</b>: ${esc(fmt(m.parsed))}${m.tags && m.tags.length ? ` <span class="tag">(${esc(m.tags.join(', '))})</span>` : ''}
      ${m.raw ? `<small>${esc(m.raw.slice(0, 160))}</small>` : ''}</div></div>`; }).join('');
    c.innerHTML = `<div class="pic"><img src="${esc(d.image)}" alt="${esc(d.style)} image for this task" loading="lazy">
      <span class="btns"><button type="button" class="bk">Show answer key</button>${d.overlay ? `<button type="button" class="bo">Show ${esc(d.overlay_by)}’s answer</button>` : ''}</span></div>
      <div class="body"><div class="meta"><span class="chip">${esc(d.skill)}</span><span class="chip">${esc(d.style)}</span>
      <span class="chip">difficulty ${d.level}/5</span>${d.frontier ? '<span class="chip">batched protocol</span>' : ''}${d.pair ? `<span class="chip">${d.variant === 'base' ? 'pair: original' : 'pair: twin'}</span>` : ''}</div>
      ${d.variant === 'counterfactual' ? `<div class="gold">What changed from the original: <b>${esc(d.change)}</b>. Everything else is identical, so the correct answer changes.</div>` : ''}
      <div class="q">${esc(d.question)}</div><div class="gold">Answer key (from the simulation): <b>${esc(fmt(d.answer))}</b></div>
      <div class="ans">${rows}</div>${d.stories && d.stories.length ? `<div class="gold"><b>What ${esc(d.overlay_by || 'the model')}’s mistake would mean:</b> ${d.stories.map(esc).join(' ')}</div>` : ''}</div>`;
    const img = c.querySelector('img'), bk = c.querySelector('.bk'), bo = c.querySelector('.bo');
    const showImg = (src) => { img.src = src; bk.textContent = src === d.reveal ? 'Hide answer key' : 'Show answer key';
      if (bo) bo.textContent = src === d.overlay ? 'Hide ' + d.overlay_by + '’s answer' : 'Show ' + d.overlay_by + '’s answer'; };
    bk.onclick = () => showImg(img.getAttribute('src') === d.reveal ? d.image : d.reveal);
    if (bo) bo.onclick = () => showImg(img.getAttribute('src') === d.overlay ? d.image : d.overlay);
    L.appendChild(c);
  });
  document.getElementById('stats').textContent = `${n} tasks · ${right} of ${total} model answers right (baselines not counted)`;
}
[fs, fy, fr].forEach(e => e.onchange = render); render();

// ---- Try it yourself: same scoring rules as the models (exact set, single choice, compass, number within tolerance)
const TRY = JSON.parse(document.getElementById('trydata').textContent || '[]');
const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
const tryScore = (d, v) => d.scoring === 'set' ? JSON.stringify([...v].sort()) === JSON.stringify([...d.answer].sort())
  : d.scoring === 'number' ? (v !== null && Math.abs(v - d.answer) <= d.tol) : v === d.answer;
let you = 0, done = 0;
function tally(){ const g = TRY.filter(d => d.model_right).length;
  document.getElementById('tally').textContent = done ? `You: ${you} of ${done} checked · ${TRY[0].model}: ${g} of ${TRY.length} on these questions` : `${TRY.length} questions · ${TRY[0].model} got ${g} right`; }
if (TRY.length) {
  const L = document.getElementById('trylist');
  TRY.forEach((d, k) => {
    const c = document.createElement('article'); c.className = 'card';
    let inp = '';
    const opts = d.scoring === 'compass' ? COMPASS : d.options;
    if (d.scoring === 'set') inp = '<div class="opts">' + opts.map(o => `<label><input type="checkbox" value="${esc(o)}"> ${esc(o)}</label>`).join('') + '</div><p class="gold">Tick all that apply (none is allowed).</p>';
    else if (d.scoring === 'number') inp = `<p><input type="number" step="0.1" class="num" aria-label="your answer"> ${esc(d.unit)}</p>`;
    else inp = '<div class="opts">' + opts.map(o => `<label><input type="radio" name="t${k}" value="${esc(o)}"> ${esc(o)}</label>`).join('') + '</div>';
    c.innerHTML = `<div class="pic"><a href="${esc(d.image)}" target="_blank" rel="noopener"><img src="${esc(d.image)}" alt="${esc(d.skill)} question image" loading="lazy"></a></div>
      <div class="body"><div class="meta"><span class="chip">${esc(d.skill)}</span>${d.variant ? `<span class="chip">${d.variant === 'base' ? 'pair: original' : 'pair: twin'}</span>` : ''}</div>
      ${d.variant === 'counterfactual' ? `<div class="gold">Same place as the question above, with one change: <b>${esc(d.change)}</b>.</div>` : ''}
      <div class="gold">${esc(d.ctx)}</div><div class="q">${esc(d.q)}</div>${inp}
      <p><button type="button" class="chk">Check my answer</button></p><div class="res" aria-live="polite"></div></div>`;
    c.querySelector('.chk').onclick = () => {
      let v;
      if (d.scoring === 'set') v = [...c.querySelectorAll('input[type=checkbox]:checked')].map(e => e.value);
      else if (d.scoring === 'number') { const x = c.querySelector('.num').value; if (x === '') return; v = parseFloat(x); }
      else { const e = c.querySelector('input[type=radio]:checked'); if (!e) return; v = e.value; }
      const ok = tryScore(d, v); you += ok ? 1 : 0; done += 1; tally();
      c.querySelectorAll('input, .chk').forEach(e => e.disabled = true);
      c.querySelector('img').src = d.reveal;
      c.querySelector('.res').innerHTML = `<div class="row"><span class="mark ${ok ? 'ok' : 'bad'}">${ok ? '✓' : '✗'}</span><div><b>You</b>: ${esc(fmt(v))}</div></div>
        <div class="row"><span class="mark ${d.model_right ? 'ok' : 'bad'}">${d.model_right ? '✓' : '✗'}</span><div><b>${esc(d.model)}</b>: ${esc(fmt(d.model_answer))}</div></div>
        <div class="gold">Answer key (from the simulation): <b>${esc(fmt(d.answer))}</b>. The image now shows the true water path.</div>`;
    };
    L.appendChild(c);
  });
  tally();
}
</script>
"""

if __name__ == "__main__":
    main()
