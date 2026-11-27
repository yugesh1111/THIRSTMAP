"""Draw the water's path (thirstmap/paths.py): the model traces the wastewater's route as points on the image and
lists the villages it reaches; the route is scored against the simulated path, cell by cell.

The images are exactly those of the frontier check (results/frontier*/img, 768 px), so the route a model draws can be
set against the villages it named before, and against the villages it names in the same reply. Five of them are
before-and-after pairs where only the outfall moved: the drawn route must move with it.

Every image is rebuilt from its seed and re-rendered, and must match the published dataset image pixel for pixel
before its truth record is written; the record keeps the renderer's own cell-to-pixel mapping.

Usage:
  python3 trace_task.py build
  OPENAI_API_KEY=proxy-injected python3 trace_task.py run --models "openai:gemini-3.5-flash@https://..." --pairs-only --budget 10
  python3 trace_task.py run --models hf:Qwen/Qwen2.5-VL-3B-Instruct
  python3 trace_task.py report
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from thirstmap import paths, render_map, render_sat  # noqa: E402
from thirstmap.dataset import STYLE_INTRO  # noqa: E402
from thirstmap.rebuild import rebuild  # noqa: E402
from thirstmap.scoring import _labels  # noqa: E402

SETS = ["results/frontier/set.json", "results/frontier_pairs/set.json"]


def short(m):
    return m.split(":", 1)[-1].split("/")[-1].split("@")[0]


# ---------------------------------------------------------------------------------------------------------------------
def build(a):
    ds, out = Path(a.dataset), Path(a.out)
    tasks = {json.loads(l)["task_id"]: json.loads(l) for l in open(ds / "tasks.jsonl")}
    from audit_labels import title
    (out / "img").mkdir(parents=True, exist_ok=True)
    items = []
    for f in SETS:
        S = json.loads(Path(f).read_text())
        for img in S["images"]:
            key = img["image"]
            sid, style = key.split("__")
            q1 = f"{sid}__Q1__{style}"
            if style not in ("map", "satellite") or q1 not in img["tasks"]:
                continue
            t = tasks[q1]
            r = rebuild(ds, sid)
            s, p, nm, P, k = r["s"], r["p"], r["nm"], r["P"], r["key"]
            tag = title(k, s)
            if style == "satellite":
                im = render_sat.render(s, p, nm, P, title=f"{tag} | satellite-style | {s['drain_note'].lower()}")
                arr, F = np.asarray(im.convert("RGB")), paths.frame_sat()
            else:
                fig = render_map.render(s, p, nm, P, title=f"{tag} | topographic map")
                arr, F = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy(), paths.frame_map(fig)
                plt.close(fig)
            pub = np.asarray(Image.open(ds / t["image"]).convert("RGB"))
            if not np.array_equal(arr, pub):
                raise SystemExit(f"{key}: re-render differs from the published image; not building its truth")
            T = paths.truth_record(s, F, style, f"img/{key}.png")
            T["villages"] = {nm["village"][v]: int(v) for v in p["villages"]}
            shutil.copy(Path(f).parent / img["file"], out / "img" / f"{key}.png")
            pair = sid.removesuffix("_cf")
            items.append(dict(task_id=f"{key}__trace", image=f"img/{key}.png", full_image=t["image"], scene_id=sid, style=style,
                              level=t["level"], terrain=t["terrain"], pair=pair,
                              prompt=f"{STYLE_INTRO[style].format(drain=s['drain_note'])}\n\nTask: {paths.PROMPT}",
                              villages_answer=t["answer"], options=t["options"], from_set=f, truth=T))
            print(f"{key}: route {len(T['path'])} cells, villages {t['answer']}", flush=True)
    paired = {it["pair"] for it in items if it["scene_id"].endswith("_cf")}
    for it in items:
        it["in_pair"] = it["pair"] in paired and any(o["scene_id"] == it["pair"] for o in items)
    with open(out / "tasks.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")
    base = {it["task_id"]: {name: paths.score(fn(it["truth"]), it["truth"]) for name, fn in
                            (("oracle (the true path)", paths.oracle), ("straight line south", paths.straight_south),
                             ("straight line to the true exit", paths.straight_to_exit))} for it in items}
    (out / "baselines.json").write_text(json.dumps(base, indent=1))
    sums = {str(q.relative_to(out)): hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted((out / "img").glob("*.png"))}
    (out / "SHA256SUMS.json").write_text(json.dumps(sums, indent=0))
    print(f"{len(items)} images ({sum(it['in_pair'] for it in items)} in before-and-after pairs) -> {out}")


# ---------------------------------------------------------------------------------------------------------------------
def score(task, raw):
    T = task["truth"]
    pts = paths.parse(raw)
    sc = paths.score(pts, T)
    listed = paths.parse_villages(raw)
    got = _labels(listed, task["options"]) if listed is not None else None
    own = paths.villages_on_line(pts, T) if pts else []
    v_ok = got is not None and set(got) == set(task["villages_answer"])
    quad = ("right route, right villages" if sc["passed"] and v_ok else
            "right route, wrong villages" if sc["passed"] else
            "wrong route, right villages" if v_ok else "wrong route, wrong villages")
    return dict(path=pts, **{k: v for k, v in sc.items()}, villages=got, villages_ok=bool(v_ok), own_line_villages=own,
                consistent=got is not None and set(got) == set(own), quadrant=quad,
                verdict=f"{'PASS' if sc['passed'] else 'fail'} P={sc['precision']:.2f} R={sc['recall']:.2f} villages {'ok' if v_ok else 'wrong'}")


def run(a):
    from cloud_task import run_requests
    ds = Path(a.dataset)
    items = [json.loads(l) for l in open(ds / "tasks.jsonl")]
    if a.pairs_only:
        items = [it for it in items if it["in_pair"]]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for spec in a.models:
        run_requests(spec, items, out, ds, a.budget, score, max_new_tokens=900)
    report(a)


# ---------------------------------------------------------------------------------------------------------------------
def overlay(task, rec, ds, out_file):
    """The full-size image with the true route (red) and the model's route (yellow), and the verdict underneath."""
    im = Image.open(ds / task["full_image"] if (ds / task["full_image"]).exists() else Path("dataset") / task["full_image"]).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    T = task["truth"]
    true_xy = [tuple(v / 1000 * s for v, s in zip(paths.cell_to_norm(i, T["frame"]), (W, H))) for i in T["path"]]
    d.line(true_xy, fill=(235, 30, 30, 170), width=7, joint="curve")
    pts = rec.get("path") or []
    xy = [(x / 1000 * W, y / 1000 * H) for x, y in pts]
    if len(xy) >= 2:
        d.line(xy, fill=(0, 0, 0, 220), width=6, joint="curve")
        d.line(xy, fill=(255, 225, 40, 255), width=3, joint="curve")
        for x, y in xy:
            d.ellipse([x - 3.5, y - 3.5, x + 3.5, y + 3.5], fill=(255, 225, 40, 255), outline=(0, 0, 0, 255))
    bar = 64
    canvas = Image.new("RGB", (W, H + bar), (18, 20, 24))
    canvas.paste(im, (0, 0))
    dd = ImageDraw.Draw(canvas)
    from thirstmap.render_sat import dejavu
    f, fs = dejavu(16), dejavu(13, bold=False)
    head = f"{short(rec['model'])}: {'route right' if rec['passed'] else 'route wrong'}"
    if rec.get("failure"):
        head += f" ({rec['failure']})"
    dd.text((10, H + 8), head, font=f, fill=(255, 225, 40) if rec["passed"] else (255, 140, 120))
    named = ", ".join(rec.get("villages") or []) or "none"
    dd.text((10, H + 34), f"on the true path: {rec['precision']:.0%} of its line · covers {rec['recall']:.0%} of the route · "
            f"names {named} ({'right' if rec['villages_ok'] else 'wrong'}; truth {', '.join(task['villages_answer']) or 'none'})",
            font=fs, fill=(225, 225, 225))
    canvas.save(out_file, quality=86)


def report(a):
    ds, out = Path(a.dataset), Path(a.out)
    items = {json.loads(l)["task_id"]: json.loads(l) for l in open(ds / "tasks.jsonl")}
    f = out / "responses.jsonl"
    rows = [r for r in map(json.loads, open(f)) if not r.get("error")] if f.exists() else []
    for r in rows:
        r.update(score(items[r["task_id"]], r["raw"]))
    figs = Path(a.docs)
    figs.mkdir(parents=True, exist_ok=True)
    S = {}
    for m in sorted({r["model"] for r in rows}):
        R = [r for r in rows if r["model"] == m]
        q = {k: sum(r["quadrant"] == k for r in R) for k in ("right route, right villages", "right route, wrong villages",
                                                             "wrong route, right villages", "wrong route, wrong villages")}
        fails = {}
        for r in R:
            if r.get("failure"):
                fails[r["failure"]] = fails.get(r["failure"], 0) + 1
        by = {items[r["task_id"]]["scene_id"]: r for r in R}
        pairs = [(by[b], by[b + "_cf"]) for b in {it["pair"] for it in items.values() if it["in_pair"]} if b in by and b + "_cf" in by]
        S[m] = dict(n=len(R), passed=sum(r["passed"] for r in R), parsed=sum(r["parse_ok"] for r in R),
                    mean_precision=round(float(np.mean([r["precision"] for r in R])), 3),
                    mean_recall=round(float(np.mean([r["recall"] for r in R])), 3),
                    villages_ok=sum(r["villages_ok"] for r in R), consistent=sum(r["consistent"] for r in R),
                    quadrants=q, failures=fails, pairs=len(pairs), pairs_both_routes=sum(x["passed"] and y["passed"] for x, y in pairs),
                    curve={t: dict(precision=round(float(np.mean([r["curve"][t]["precision"] for r in R if r.get("curve")] or [0])), 3),
                                   recall=round(float(np.mean([r["curve"][t]["recall"] for r in R if r.get("curve")] or [0])), 3))
                           for t in map(str, paths.CURVE)})
        for r in R:
            overlay(items[r["task_id"]], r, Path("dataset"), figs / f"{short(m)}__{items[r['task_id']]['task_id'].removesuffix('__trace')}.jpg")
    base = json.loads((ds / "baselines.json").read_text()) if (ds / "baselines.json").exists() else {}
    B = {}
    for per in base.values():
        for name, sc in per.items():
            b = B.setdefault(name, dict(n=0, passed=0, p=[], r=[]))
            b["n"] += 1
            b["passed"] += sc["passed"]
            b["p"].append(sc["precision"])
            b["r"].append(sc["recall"])
    (out / "summary.json").write_text(json.dumps(dict(models=S, baselines={k: dict(n=v["n"], passed=v["passed"],
                                                                                   mean_precision=round(float(np.mean(v["p"])), 3),
                                                                                   mean_recall=round(float(np.mean(v["r"])), 3))
                                                                          for k, v in B.items()}), indent=1))
    L = ["# Draw the water's path", "",
         f"The model traces the wastewater's route from outfall O as points on the image and lists the villages it reaches. "
         f"A route passes when at least {paths.PASS:.0%} of the drawn line lies within {paths.TOL} cells ({paths.TOL * 25} m) of "
         f"the simulated path and the line covers at least {paths.PASS:.0%} of the path. Tasks and truth: `eval_set/trace/`.", "",
         "| Model | Routes | Route right | On the path (precision) | Route covered (recall) | Villages right | Villages match its own line | Pairs: both routes right |",
         "|---|---|---|---|---|---|---|---|"]
    for m, x in S.items():
        L.append(f"| {m} | {x['n']} | **{x['passed']}** | {x['mean_precision']:.0%} | {x['mean_recall']:.0%} | {x['villages_ok']} | "
                 f"{x['consistent']} | {x['pairs_both_routes']} of {x['pairs']} |")
    L += ["", "**Reference lines** (no model; every image):", "", "| Line | Passes | Precision | Recall |", "|---|---|---|---|"]
    for k, v in B.items():
        L.append(f"| {k} | {v['passed']} of {v['n']} | {np.mean(v['p']):.0%} | {np.mean(v['r']):.0%} |")
    L += ["", "**Answer vs route**, per reply:", "", "| Model | Right route, right villages | Right route, wrong villages | "
          "Wrong route, right villages | Wrong route, wrong villages |", "|---|---|---|---|---|"]
    for m, x in S.items():
        q = x["quadrants"]
        L.append(f"| {m} | {q['right route, right villages']} | {q['right route, wrong villages']} | "
                 f"**{q['wrong route, right villages']}** | {q['wrong route, wrong villages']} |")
    L += ["", "**How the wrong routes went wrong:**", ""]
    for m, x in S.items():
        if x["failures"]:
            L.append(f"- {m}: " + ", ".join(f"{n} × {k}" for k, n in sorted(x["failures"].items(), key=lambda kv: -kv[1])))
    L += ["", f"Every route drawn over its image (true route red, the model's yellow): `{figs}/`."]
    (out / "REPORT.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--dataset", default="dataset"); b.add_argument("--out", default="eval_set/trace")
    r = sub.add_parser("run")
    r.add_argument("--dataset", default="eval_set/trace"); r.add_argument("--out", default="results/trace")
    r.add_argument("--docs", default="docs/trace")
    r.add_argument("--models", nargs="+", required=True)
    r.add_argument("--pairs-only", action="store_true", help="only the before-and-after pairs (10 images)")
    r.add_argument("--budget", type=int, default=20)
    p = sub.add_parser("report")
    p.add_argument("--dataset", default="eval_set/trace"); p.add_argument("--out", default="results/trace")
    p.add_argument("--docs", default="docs/trace")
    a = ap.parse_args()
    {"build": build, "run": run, "report": report}[a.cmd](a)


if __name__ == "__main__":
    main()
