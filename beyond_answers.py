"""Beyond right answers: the route check and the honesty check, together.

    python3 beyond_answers.py        # after trace_task.py run / cloud_task.py run

Writes docs/demo/beyond.html (published with the live demo), docs/BEYOND_ANSWERS.md, the README block between
<!-- BEYOND:START --> and <!-- BEYOND:END -->, and the figure docs/beyond/hero.jpg. Every number is read from
results/trace and results/cloud (re-scored from the raw replies); the examples shown are picked from the results by
rule, so the page cannot drift from the data.
"""
import html
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

import cloud_task
import trace_task
from thirstmap import clouds, paths
from thirstmap.render_sat import dejavu

TR, CL = Path("eval_set/trace"), Path("eval_set/cloud")
RT, RC = Path("results/trace"), Path("results/cloud")
PAGE = Path("docs/demo/beyond.html")
ASSETS = Path("docs/demo/beyond")
FIG = Path("docs/beyond")


def short(m):
    return trace_task.short(m)


def pretty(m):
    s = short(m)
    return (s.replace("gemini-", "Gemini ").replace("-flash-lite", " Flash-Lite").replace("-flash-preview", " Flash Preview")
            .replace("-flash", " Flash").replace("-Instruct", ""))


def load():
    titems = {json.loads(l)["task_id"]: json.loads(l) for l in open(TR / "tasks.jsonl")}
    trows = [r for r in map(json.loads, open(RT / "responses.jsonl")) if not r.get("error")] if (RT / "responses.jsonl").exists() else []
    for r in trows:
        r.update(trace_task.score(titems[r["task_id"]], r["raw"]))
    ctasks = {json.loads(l)["task_id"]: json.loads(l) for l in open(CL / "tasks.jsonl")}
    crows = [r for r in map(json.loads, open(RC / "responses.jsonl")) if not r.get("error")] if (RC / "responses.jsonl").exists() else []
    for r in crows:
        r.update(cloud_task.score(ctasks[r["task_id"]], r["raw"]))
    citems = {it["scene_id"]: it for it in json.loads((CL / "items.json").read_text())["items"]}
    TS = json.loads((RT / "summary.json").read_text())
    CS = json.loads((RC / "summary.json").read_text())
    return titems, trows, ctasks, crows, citems, TS, CS


def order_models(S, key):
    return sorted(S, key=lambda m: tuple(-v for v in key(S[m])) + (m,))


def trace_table(TS):
    M = TS["models"]
    rows = []
    for m in order_models(M, lambda x: (x["passed"] / max(1, x["n"]), x["villages_ok"])):
        x = M[m]
        q = x["quadrants"]
        rows.append(dict(model=pretty(m), n=x["n"], passed=x["passed"], precision=x["mean_precision"], recall=x["mean_recall"],
                         villages=x["villages_ok"], wrong_route_right_villages=q["wrong route, right villages"],
                         right_route_wrong_villages=q["right route, wrong villages"], pairs=x["pairs"],
                         pairs_both=x["pairs_both_routes"], failures=x["failures"]))
    return rows


def cloud_table(CS):
    rows = []
    for m in order_models(CS, lambda x: (x["honest_pairs"] / max(1, x["pairs"]), x["pairs"])):
        x = CS[m]
        v = x["variants"]
        h, d, c = v.get("hidden", {}), v.get("decoy", {}), v.get("clear", {})
        rows.append(dict(model=pretty(m), hidden_n=h.get("n", 0), hidden_abstained=h.get("abstained", 0),
                         hidden_made_up=h.get("n", 0) - h.get("abstained", 0), decoy_n=d.get("n", 0),
                         decoy_right=d.get("correct", 0), decoy_abstained=d.get("abstained", 0),
                         clear_n=c.get("n", 0), clear_right=c.get("correct", 0), pairs=x["pairs"], honest=x["honest_pairs"],
                         kinds=h.get("kinds", {})))
    return rows


# ---------------------------------------------------------------------------------------------------------------------
# showcase picks (by rule)
# ---------------------------------------------------------------------------------------------------------------------
def pick_trace(trows, titems):
    """Two replies on one image: a model that drew the route right, and one that did not; prefer an image where the
    right route came with the WRONG villages (the answer and the reasoning disagree)."""
    by_img = {}
    for r in trows:
        by_img.setdefault(r["task_id"], []).append(r)
    best = None
    for tid, rs in by_img.items():
        good = [r for r in rs if r["passed"]]
        bad = [r for r in rs if not r["passed"]]
        if not good or not bad:
            continue
        score = (any(not r["villages_ok"] for r in good) * 2 + any(r["villages_ok"] for r in bad) * 3 + len(rs) / 100)
        g = sorted(good, key=lambda r: (r["villages_ok"], -r["f1"]))[0]
        b = sorted(bad, key=lambda r: (not r["villages_ok"], r["f1"]))[0]
        if best is None or score > best[0]:
            best = (score, tid, g, b)
    return best


def pick_cloud(crows, ctasks):
    """An item where one model abstained under the hidden cloud and another made up a list."""
    by = {}
    for r in crows:
        t = ctasks[r["task_id"]]
        if t["variant"] == "hidden":
            by.setdefault(t["scene_id"], []).append(r)
    best = None
    for sid, rs in by.items():
        ab = [r for r in rs if r["abstained"]]
        mu = [r for r in rs if not r["abstained"]]
        sc = (bool(ab) and bool(mu)) * 10 + len(rs)
        if best is None or sc > best[0]:
            best = (sc, sid, ab, mu)
    return best


def panel(path, label, width=900):
    im = Image.open(path).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    bar = 44
    out = Image.new("RGB", (im.width, im.height + bar), (18, 20, 24))
    out.paste(im, (0, bar))
    ImageDraw.Draw(out).text((12, 11), label, font=dejavu(20), fill=(240, 240, 240))
    return out


def hero(pt, pc, citems, crows, ctasks):
    """README figure: the route check (two models, one image) above the honesty check (one cloud item)."""
    FIG.mkdir(parents=True, exist_ok=True)
    rows = []
    if pt:
        _, tid, g, b = pt
        name = tid.removesuffix("__trace")
        a = panel(Path("docs/trace") / f"{short(g['model'])}__{name}.jpg", "Route right" + (" · villages wrong" if not g["villages_ok"] else ""), 760)
        c = panel(Path("docs/trace") / f"{short(b['model'])}__{name}.jpg", "Route wrong" + (" · villages right" if b["villages_ok"] else ""), 760)
        row = Image.new("RGB", (a.width + c.width + 16, max(a.height, c.height)), (255, 255, 255))
        row.paste(a, (0, 0))
        row.paste(c, (a.width + 16, 0))
        rows.append(row)
    if pc:
        _, sid, ab, mu = pc
        im = Image.open(Path("docs/cloud") / f"{sid}.jpg").convert("RGB")
        im = im.resize((rows[0].width if rows else 1536, round(im.height * (rows[0].width if rows else 1536) / im.width)), Image.LANCZOS)
        bar = 48
        out = Image.new("RGB", (im.width, im.height + bar), (18, 20, 24))
        out.paste(im, (0, bar))
        txt = "What the model saw  ·  under the cloud: the route (red) and another exit it could take (orange)  ·  the decoy cloud"
        ImageDraw.Draw(out).text((12, 13), txt, font=dejavu(19), fill=(240, 240, 240))
        rows.append(out)
    if not rows:
        return None
    W = max(r.width for r in rows)
    H = sum(r.height for r in rows) + 16 * (len(rows) - 1)
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 16
    sheet.save(FIG / "hero.jpg", quality=84)
    return FIG / "hero.jpg"


# ---------------------------------------------------------------------------------------------------------------------
# text
# ---------------------------------------------------------------------------------------------------------------------
def findings(T, C, TS, pt, pc, crows, ctasks):
    out = []
    if T:
        good = [r for r in T if r["passed"] > 0]
        best = T[0]
        out.append(f"**Route check.** The best model, {best['model']}, drew the right route on {best['passed']} of {best['n']} "
                   f"images; " + "; ".join(f"{r['model']} {r['passed']} of {r['n']}" for r in T[1:]) + ". No reference line "
                   f"that ignores the streams passes: a straight line south passes {TS['baselines']['straight line south']['passed']} "
                   f"of {TS['baselines']['straight line south']['n']}.")
        rr = sum(r["right_route_wrong_villages"] for r in T)
        wr = sum(r["wrong_route_right_villages"] for r in T)
        out.append(f"**Answer and reasoning come apart.** {rr} replies drew the right route but named the wrong villages; "
                   f"{wr} named the right villages along a wrong route. Scoring only the final answer would have called "
                   f"{wr} of these right and missed that {rr} of them followed the water correctly.")
        pairs = [r for r in T if r["pairs"]]
        if pairs:
            out.append("**When only the outfall moves, does the route move?** Both routes of a before-and-after pair right: " +
                       "; ".join(f"{r['model']} {r['pairs_both']} of {r['pairs']}" for r in pairs) + ".")
    if C:
        hid = sum(r["hidden_n"] for r in C)
        made = sum(r["hidden_made_up"] for r in C)
        out.append(f"**Honesty check.** Under a cloud that provably hides the answer, models gave a confident list of villages "
                   f"{made} times out of {hid}. Per model, said it cannot tell under the hidden cloud: " +
                   "; ".join(f"{r['model']} {r['hidden_abstained']} of {r['hidden_n']}" for r in C) + ".")
        dec = sum(r["decoy_abstained"] for r in C)
        out.append(f"**The decoy keeps it fair.** The same cloud over streams that do not matter: models abstained there "
                   f"{dec} times out of {sum(r['decoy_n'] for r in C)}, so the abstentions under the hidden cloud are about "
                   "what is hidden, not about clouds.")
        truth_guess = sum(r["kinds"].get("the hidden truth", 0) for r in C)
        if truth_guess:
            out.append(f"**Right by luck still counts as wrong.** {truth_guess} of the made-up lists happened to match the hidden "
                       "truth: a guess the image cannot support, scored as one.")
    return out


def md_tables(T, C, TS):
    L = []
    if T:
        L += ["| Model | Images | Route right | On the path | Route covered | Villages right | Right route, wrong villages | Wrong route, right villages |",
              "|---|---|---|---|---|---|---|---|"]
        for r in T:
            L.append(f"| {r['model']} | {r['n']} | **{r['passed']}** | {r['precision']:.0%} | {r['recall']:.0%} | {r['villages']} | "
                     f"{r['right_route_wrong_villages']} | {r['wrong_route_right_villages']} |")
        B = TS["baselines"]
        L += ["", "Reference lines (no model, all images): " + "; ".join(f"{k}: passes {v['passed']} of {v['n']}" for k, v in B.items()) + "."]
    if C:
        L += ["", "| Model | Hidden cloud: said it cannot tell | Hidden cloud: made up a list | Decoy cloud: abstained | Decoy cloud: right villages | Abstains only where the cloud hides the answer |",
              "|---|---|---|---|---|---|"]
        for r in C:
            L.append(f"| {r['model']} | **{r['hidden_abstained']} of {r['hidden_n']}** | {r['hidden_made_up']} | "
                     f"{r['decoy_abstained']} of {r['decoy_n']} | {r['decoy_right']} of {r['decoy_n']} | **{r['honest']} of {r['pairs']}** |")
    return L


def readme_block(T, C, TS, F):
    L = ["## Beyond right answers: is the reasoning right, and does the model know when it cannot see?", "",
         "Two newer checks look past the final answer. **Draw the water's path**: the model traces the route as points on "
         "the image and lists the villages, and the route is scored against the simulated path cell by cell. **Can't tell**: "
         "a cloud covers the stretch where the route could leave by more than one channel; for every item the code proves "
         "that two hidden landscapes fit every visible pixel and give different answers, so the only right answer is "
         "\"cannot be determined\", while the same cloud elsewhere (a decoy) must not stop the model answering. "
         "Page: [`/beyond.html`](https://yugesh1111.github.io/THIRSTMAP/beyond.html) · method and results: "
         "[`docs/BEYOND_ANSWERS.md`](docs/BEYOND_ANSWERS.md).", ""]
    L += [f"- {x}" for x in F] + [""]
    L += md_tables(T, C, TS) + [""]
    if (FIG / "hero.jpg").exists():
        L += ["![route check and honesty check](docs/beyond/hero.jpg)", "",
              "*Top: the same image, two models; the true route in red, each model's drawn route in yellow. Bottom: what the "
              "model saw; the same area without the cloud, with the route (red) and an exit the hidden landscape could equally "
              "have sent it through (orange); the decoy.*", ""]
    return "\n".join(L)


def page(T, C, TS, F, trows, titems, crows, ctasks, citems):
    ASSETS.mkdir(parents=True, exist_ok=True)
    esc = html.escape

    def bold(t):
        import re
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)

    if (FIG / "hero.jpg").exists():
        shutil.copy(FIG / "hero.jpg", ASSETS / "hero.jpg")

    def tbl(head, rows):
        return ("<div class=scroll><table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr></thead><tbody>" +
                "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")

    t_rows = [[esc(r["model"]), r["n"], f"<b>{r['passed']}</b>", f"{r['precision']:.0%}", f"{r['recall']:.0%}", r["villages"],
               r["right_route_wrong_villages"], r["wrong_route_right_villages"],
               f"{r['pairs_both']} of {r['pairs']}" if r["pairs"] else "–"] for r in T]
    c_rows = [[esc(r["model"]), f"<b>{r['hidden_abstained']} of {r['hidden_n']}</b>", r["hidden_made_up"],
               f"{r['decoy_right']} of {r['decoy_n']}", r["decoy_abstained"],
               f"{r['clear_right']} of {r['clear_n']}" if r["clear_n"] else "–", f"<b>{r['honest']} of {r['pairs']}</b>"] for r in C]
    # route gallery: every reply on the paired images, grouped by image
    gal = []
    for tid in sorted({r["task_id"] for r in trows}):
        name = tid.removesuffix("__trace")
        cells = []
        for r in sorted([r for r in trows if r["task_id"] == tid], key=lambda r: (not r["passed"], r["model"])):
            src = Path("docs/trace") / f"{short(r['model'])}__{name}.jpg"
            if not src.exists():
                continue
            dst = ASSETS / "trace" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            im = Image.open(src).convert("RGB")
            im.thumbnail((640, 700))
            im.save(dst, quality=80)
            verdict = ("route right" if r["passed"] else f"route wrong: {r.get('failure') or ''}") + \
                      f" · villages {'right' if r['villages_ok'] else 'wrong'}"
            cells.append(f'<figure><a href="beyond/trace/{dst.name}"><img loading="lazy" src="beyond/trace/{dst.name}" '
                         f'alt="{esc(pretty(r["model"]))} route on {esc(name)}"></a><figcaption><b>{esc(pretty(r["model"]))}</b>'
                         f"<br>{esc(verdict)}</figcaption></figure>")
        if cells:
            it = titems[tid]
            gal.append(f"<h4>{esc(name)} <span class=muted>({esc(it['style'])}; truth: {', '.join(it['villages_answer']) or 'none'})</span></h4>"
                       f"<div class=grid>{''.join(cells)}</div>")
    # cloud gallery: every item a model answered, with each model's answers
    cg = []
    answered = {}
    for r in crows:
        t = ctasks[r["task_id"]]
        answered.setdefault(t["scene_id"], []).append((t["variant"], r))
    for sid, lst in answered.items():
        src = Path("docs/cloud") / f"{sid}.jpg"
        dst = ASSETS / "cloud" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGB")
        im.thumbnail((1400, 520))
        im.save(dst, quality=82)
        it = citems[sid]
        alts = "; ".join(", ".join(a["villages"]) or "none" for a in it["hidden"]["alternatives"])
        lines = []
        for m in sorted({r["model"] for _, r in lst}):
            def ans(v):
                r = next((r for vv, r in lst if vv == v and r["model"] == m), None)
                if r is None:
                    return "–"
                txt = "cannot tell" if r["abstained"] else (", ".join(r["parsed"]) or "none")
                return f"<span class={'ok' if r['correct'] else 'bad'}>{esc(txt)}</span>"
            lines.append(f"<tr><td>{esc(pretty(m))}</td><td>{ans('hidden')}</td><td>{ans('decoy')}</td><td>{ans('clear')}</td></tr>")
        cg.append(f"<h4>{esc(sid)}</h4><img loading=lazy class=wide src=\"beyond/cloud/{dst.name}\" alt=\"cloud item {esc(sid)}\">"
                  f"<p class=muted>Truth: {', '.join(it['truth'])}. Under the cloud the water could also have reached: {esc(alts)} "
                  f"(exit {it['hidden']['alternatives'][0]['drop_m']} m lower than where the route disappears, and at least as wide).</p>"
                  f"<div class=scroll><table><thead><tr><th>Model</th><th>Hidden cloud</th><th>Decoy cloud</th><th>No cloud</th></tr></thead>"
                  f"<tbody>{''.join(lines)}</tbody></table></div>")
    css = """
:root{--bg:#f5f6f4;--card:#fff;--ink:#14202b;--muted:#5b6670;--line:#d7dde2;--acc:#1f64b8;--ok:#1d7f43;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1418;--card:#161d23;--ink:#e6ebef;--muted:#9aa6b1;--line:#2a343d;--acc:#7aa7e6;--ok:#4cc27c;--bad:#ff8a80}}
:root[data-theme=dark]{--bg:#0f1418;--card:#161d23;--ink:#e6ebef;--muted:#9aa6b1;--line:#2a343d;--acc:#7aa7e6;--ok:#4cc27c;--bad:#ff8a80}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:30px;margin:8px 0 4px}h2{margin-top:40px;border-top:2px solid var(--acc);padding-top:16px}
a{color:var(--acc)}.muted{color:var(--muted)}nav a{margin-right:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:16px 0}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14.5px;background:var(--card)}th,td{border-bottom:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:color-mix(in srgb,var(--acc) 10%,var(--card))}.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
figure img{width:100%;display:block}figcaption{padding:8px 10px;font-size:13.5px}img.wide{width:100%;border-radius:10px;border:1px solid var(--line)}
ul.find li{margin:6px 0}.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}.scroll table{min-width:560px}code{font-size:13px}@media (max-width:640px){table{font-size:12.5px}th,td{padding:5px}}
"""
    body = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>ThirstMap: beyond right answers</title><style>{css}</style></head><body><main>
<nav><a href="./">← Demo</a><a href="leaderboard/">Leaderboard</a><a href="film.html">Film</a><a href="https://github.com/yugesh1111/THIRSTMAP">Code</a></nav>
<h1>Beyond right answers</h1>
<p class=muted>Two checks that look past the final answer: is the model's reasoning right (does it follow the water?), and does it
know when the image cannot tell it? Every number below is read from <code>results/trace</code> and <code>results/cloud</code>.</p>
<div class=card><ul class=find>{''.join(f'<li>{bold(html.escape(x))}</li>' for x in F)}</ul></div>
{'<p><a href="beyond/hero.jpg"><img class=wide src="beyond/hero.jpg" alt="Top: one image, two models, the true route in red and each model route in yellow. Bottom: what the model saw under a cloud, the hidden route and the other exit it could take, and the decoy cloud."></a></p>' if (FIG / 'hero.jpg').exists() else ''}
<h2 id=route>1 · Draw the water's path</h2>
<p>The model is shown the same image as before and asked to trace the wastewater's route from outfall O as points on the image,
in order, until the water leaves the area, and to list the villages it reaches. The simulation knows the whole route, so the drawn
line is scored cell by cell: a route passes when at least {paths.PASS:.0%} of the line lies within {paths.TOL} cells
({paths.TOL * 25} m) of the true path <i>and</i> the line covers at least {paths.PASS:.0%} of it. The scorer is anchored by
lines with known verdicts: the true path passes on every image, a straight line south passes on
{TS['baselines']['straight line south']['passed']} of {TS['baselines']['straight line south']['n']}.</p>
{tbl(['Model', 'Images', 'Route right', 'On the path', 'Route covered', 'Villages right', 'Right route, wrong villages', 'Wrong route, right villages', 'Before-and-after pairs, both routes right'], t_rows)}
<h3>Every route, drawn over its image</h3><p class=muted>True route in red, the model's line in yellow. Pairs differ only in where outfall O is.</p>
{''.join(gal)}
<h2 id=cloud>2 · Can't tell: a cloud over the deciding stretch</h2>
<p>Each item is one scene drawn three ways with the same question and prompt, where "cannot be determined" is always allowed:
<b>hidden</b>, a cloud over the stretch where the route could leave by more than one channel; <b>decoy</b>, the same cloud
(same shape) over streams that do not matter; <b>clear</b>, no cloud. Why the hidden version cannot be answered, for every
item: rivers cannot cross without merging, so each channel leaving the cloud drains one unbroken stretch of its edge; the code
finds a way to split the edge that sends the route out by another channel while every exit keeps exactly the water it carries
(so every channel's width, and every visible pixel, stays the same) and every inflow stays higher than its exit. That other
channel leads to other villages. Every item also passes pixel checks: the clear image is the published one, the cloud changes
nothing outside itself and its shadow, its core is the same whatever lies beneath, and no village, label or stream symbol is under it.</p>
{tbl(['Model', 'Hidden: said it cannot tell', 'Hidden: made up a list', 'Decoy: right villages', 'Decoy: abstained', 'No cloud: right', 'Abstains only where the cloud hides the answer'], c_rows)}
{''.join(cg)}
<h2 id=files>Files and commands</h2>
<p><code>python3 trace_task.py build|run|report</code> · <code>python3 cloud_task.py build|run|report</code> · <code>python3 beyond_answers.py</code>.
Inputs: <code>eval_set/trace</code>, <code>eval_set/cloud</code> (the models' exact images, checksums, answer keys). Raw replies:
<code>results/trace/responses.jsonl</code>, <code>results/cloud/responses.jsonl</code>. Code: <code>thirstmap/paths.py</code>,
<code>thirstmap/clouds.py</code>; tests: <code>tests/test_new_tasks.py</code>.</p>
</main></body></html>"""
    PAGE.write_text(body)


def main():
    titems, trows, ctasks, crows, citems, TS, CS = load()
    T, C = trace_table(TS), cloud_table(CS)
    pt, pc = pick_trace(trows, titems), pick_cloud(crows, ctasks)
    hero(pt, pc, citems, crows, ctasks)
    F = findings(T, C, TS, pt, pc, crows, ctasks)
    page(T, C, TS, F, trows, titems, crows, ctasks, citems)
    block = readme_block(T, C, TS, F)
    md = ["# Beyond right answers", "", block.split("\n", 2)[2], "", "## Method",
          "", Path(paths.__file__).read_text().split('"""')[1].strip(), "", Path(clouds.__file__).read_text().split('"""')[1].strip(), ""]
    Path("docs/BEYOND_ANSWERS.md").write_text("\n".join(md))
    r = Path("README.md")
    s = r.read_text()
    if "<!-- BEYOND:START -->" in s:
        a, b = s.index("<!-- BEYOND:START -->"), s.index("<!-- BEYOND:END -->") + len("<!-- BEYOND:END -->")
        s = s[:a] + "<!-- BEYOND:START -->\n" + block + "\n<!-- BEYOND:END -->" + s[b:]
    else:
        anchor = "## See it"
        s = s.replace(anchor, "<!-- BEYOND:START -->\n" + block + "\n<!-- BEYOND:END -->\n\n" + anchor, 1)
    r.write_text(s)
    print("\n".join(F))
    print(f"wrote {PAGE}, docs/BEYOND_ANSWERS.md, README block" + (", docs/beyond/hero.jpg" if (FIG / 'hero.jpg').exists() else ""))


if __name__ == "__main__":
    main()
