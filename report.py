"""Turn evaluation responses into findings: tables, charts, and a markdown report.

Usage: python3 report.py results/<run> [--dataset dataset]
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SKILL_ORDER = ["trace_downstream", "order_along_flow", "measure_along_flow", "nature_based_filtering",
               "siting_downstream_impact",
               "trace_upstream_catchment", "read_flow_direction", "read_elevation",
               "read_colour_scale_threshold", "read_colour_scale_value"]
SKILL_LABEL = {"trace_downstream": "Trace downstream", "order_along_flow": "Order along flow",
               "measure_along_flow": "Measure along flow",
               "nature_based_filtering": "Place wetland", "siting_downstream_impact": "Site selection",
               "trace_upstream_catchment": "Trace upstream", "read_flow_direction": "Flow direction",
               "read_elevation": "Read elevation", "read_colour_scale_threshold": "Thermal threshold",
               "read_colour_scale_value": "Thermal value"}


def _style_axes(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def acc(rows):
    return sum(r["correct"] for r in rows) / len(rows) if rows else None


def build_report(run_dir, dataset):
    run_dir, dataset = Path(run_dir), Path(dataset)
    tasks = {}
    for line in open(dataset / "tasks.jsonl"):
        t = json.loads(line)
        tasks[t["task_id"]] = t
    latest = {}
    for line in open(run_dir / "responses.jsonl"):
        r = json.loads(line)
        if r.get("error") or r["task_id"] not in tasks:
            continue
        latest[(r["model"], r["mode"], r["task_id"])] = r
    rows = [dict(r, **{k: tasks[r["task_id"]][k] for k in ("skill", "style", "level", "qid", "scene_id")})
            for r in latest.values()]
    models = sorted({r["model"] for r in rows}, key=lambda m: (m.startswith("mock"), m))
    img = [r for r in rows if r["mode"] == "image"]
    blind = [r for r in rows if r["mode"] == "blind"]

    S = dict(models=models, n_responses=len(rows))
    by = lambda rs, *keys: _group(rs, keys)
    S["overall"] = {m: dict(image=acc([r for r in img if r["model"] == m]),
                            blind=acc([r for r in blind if r["model"] == m]),
                            n=len([r for r in img if r["model"] == m])) for m in models}
    S["by_skill"] = {m: {sk: acc(v) for sk, v in by([r for r in img if r["model"] == m], "skill").items()}
                     for m in models}
    S["by_style"] = {m: {st: acc(v) for st, v in by([r for r in img if r["model"] == m], "style").items()}
                     for m in models}
    S["by_level"] = {m: {lv: acc(v) for lv, v in sorted(by([r for r in img if r["model"] == m], "level").items())}
                     for m in models}
    curves, breaking = {}, {}
    for m in models:
        curves[m], breaking[m] = {}, {}
        for sk, v in by([r for r in img if r["model"] == m], "skill").items():
            c = {lv: acc(x) for lv, x in sorted(by(v, "level").items())}
            curves[m][sk] = c
            below = [lv for lv, a in c.items() if a is not None and a < 0.5]
            breaking[m][sk] = min(below) if below else ">5"
    S["eye_exam_curves"], S["breaking_level"] = curves, breaking

    # visual necessity (V13): how much does the image help, and which tasks are guessable blind?
    S["blind_gap_by_skill"] = {}
    for m in models:
        if any(r["model"] == m for r in blind):
            gi = by([r for r in img if r["model"] == m], "skill")
            gb = by([r for r in blind if r["model"] == m], "skill")
            S["blind_gap_by_skill"][m] = {sk: (acc(gi.get(sk)), acc(gb.get(sk))) for sk in gi}
    blind_right = Counter(r["task_id"] for r in blind if r["correct"] and not r["model"].startswith("mock"))
    n_blind_models = len({r["model"] for r in blind if not r["model"].startswith("mock")})
    S["tasks_guessable_without_image"] = sorted(t for t, c in blind_right.items()
                                                if n_blind_models and c / n_blind_models > 0.5)

    # cross-style consistency: same scene + question asked on the map and on the satellite image
    S["map_vs_satellite"] = {}
    for m in models:
        pairs = defaultdict(dict)
        for r in img:
            if r["model"] == m and r["style"] in ("map", "satellite"):
                pairs[(r["scene_id"], r["qid"])][r["style"]] = r["correct"]
        both = [v for v in pairs.values() if len(v) == 2]
        if both:
            S["map_vs_satellite"][m] = dict(
                n=len(both), both_right=sum(v["map"] and v["satellite"] for v in both),
                only_map=sum(v["map"] and not v["satellite"] for v in both),
                only_satellite=sum(v["satellite"] and not v["map"] for v in both),
                both_wrong=sum(not v["map"] and not v["satellite"] for v in both))
    # error diagnosis
    S["error_tags"] = {m: dict(Counter(tg for r in img if r["model"] == m for tg in r.get("tags", [])).most_common())
                       for m in models}
    trap_rate = {}
    for m in models:
        exposed = [r for r in img if r["model"] == m and tasks[r["task_id"]].get("traps")]
        fell = [r for r in exposed if any(t.startswith("trap:") for t in r.get("tags", []))]
        trap_rate[m] = dict(exposed=len(exposed), fell=len(fell), rate=len(fell) / len(exposed) if exposed else None)
    S["trap_fall_rate"] = trap_rate
    # counterfactual pairs: same scene, one minimal change, the answer must flip
    S["counterfactual_pairs"] = {}
    for m in models:
        pairs = defaultdict(dict)
        for r in img:
            t = tasks[r["task_id"]]
            if r["model"] == m and t.get("pair_id"):
                pairs[t["pair_id"]][t["variant"]] = (r, t)
        full = [v for v in pairs.values() if len(v) == 2]
        if not full:
            continue
        by_kind = defaultdict(list)
        for v in full:
            by_kind[v["counterfactual"][1]["cf_kind"]].append(v)
        stat = lambda vs: dict(
            pairs=len(vs),
            single_task_accuracy=sum(x[0]["correct"] for v in vs for x in v.values()) / (2 * len(vs)),
            pair_accuracy=sum(v["base"][0]["correct"] and v["counterfactual"][0]["correct"] for v in vs) / len(vs),
            unchanged_answer_rate=sum(json.dumps(v["base"][0]["parsed"], sort_keys=True)
                                      == json.dumps(v["counterfactual"][0]["parsed"], sort_keys=True) for v in vs) / len(vs))
        S["counterfactual_pairs"][m] = dict(stat(full), by_kind={k: stat(v) for k, v in by_kind.items()})
    S["cost"] = {m: dict(input_tokens=sum(r.get("input_tokens") or 0 for r in rows if r["model"] == m),
                         output_tokens=sum(r.get("output_tokens") or 0 for r in rows if r["model"] == m),
                         usd=round(sum(r.get("cost_usd") or 0 for r in rows if r["model"] == m), 4),
                         mean_latency_s=round(sum(r.get("latency_s") or 0 for r in rows if r["model"] == m)
                                              / max(1, sum(r["model"] == m for r in rows)), 2))
                 for m in models}
    (run_dir / "summary.json").write_text(json.dumps(S, indent=2, default=str))
    charts(S, run_dir)
    markdown(S, run_dir)
    print(f"report written to {run_dir}")
    return S


def _group(rows, keys):
    g = defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in keys) if len(keys) > 1 else r[keys[0]]].append(r)
    return g


def charts(S, out):
    models = S["models"]
    plt.rcParams.update({"font.size": 9, "text.color": INK, "axes.labelcolor": INK2})
    # 1. accuracy by skill, one bar per model
    skills = [s for s in SKILL_ORDER if any(s in S["by_skill"][m] for m in models)]
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(skills) * max(1, len(models)) + 1.2), facecolor=SURFACE)
    h = 0.8 / len(models)
    for k, m in enumerate(models):
        ys = [i + k * h for i in range(len(skills))]
        vals = [100 * (S["by_skill"][m].get(s) or 0) for s in skills]
        ax.barh(ys, vals, height=h * 0.85, color=SERIES[k % 8], label=m, edgecolor=SURFACE, linewidth=1)
        for y, v in zip(ys, vals):
            ax.text(v + 1, y, f"{v:.0f}%", va="center", fontsize=7, color=INK2)
    ax.set_yticks([i + h * (len(models) - 1) / 2 for i in range(len(skills))])
    ax.set_yticklabels([SKILL_LABEL[s] for s in skills])
    ax.invert_yaxis()
    ax.set_xlim(0, 108)
    ax.set_xlabel("Accuracy (%)")
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("Accuracy by visual skill", loc="left", fontsize=11, color=INK)
    fig.tight_layout(); fig.savefig(out / "chart_accuracy_by_skill.png", dpi=150); plt.close(fig)

    # 2. eye exam: accuracy vs difficulty, small multiples per skill
    n = len(skills); cols = 3; rws = (n + cols - 1) // cols
    fig, axes = plt.subplots(rws, cols, figsize=(10, 2.6 * rws), facecolor=SURFACE, sharey=True)
    for ax, sk in zip(axes.flat, skills):
        for k, m in enumerate(models):
            c = S["eye_exam_curves"][m].get(sk, {})
            if c:
                xs = [int(x) for x in c]; ys = [100 * (c[x] or 0) for x in c]
                ax.plot(xs, ys, "-o", color=SERIES[k % 8], lw=2, ms=4, label=m)
        ax.axhline(50, color=INK2, lw=1, ls="--")
        ax.set_title(SKILL_LABEL[sk], fontsize=9, loc="left", color=INK)
        ax.set_xticks([1, 2, 3, 4, 5]); ax.set_ylim(-5, 105)
        _style_axes(ax); ax.grid(axis="y", color=GRID, lw=0.8)
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    axes.flat[0].legend(frameon=False, fontsize=7)
    fig.suptitle("Eye exam: accuracy (%) vs difficulty level, dashed line = 50% breaking point",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(); fig.savefig(out / "chart_eye_exam.png", dpi=150); plt.close(fig)

    # 3. accuracy by image style
    styles = [s for s in ("satellite", "map", "thermal") if any(s in S["by_style"][m] for m in models)]
    fig, ax = plt.subplots(figsize=(7, 3.2), facecolor=SURFACE)
    w = 0.8 / len(models)
    for k, m in enumerate(models):
        xs = [i + k * w for i in range(len(styles))]
        vals = [100 * (S["by_style"][m].get(s) or 0) for s in styles]
        ax.bar(xs, vals, width=w * 0.85, color=SERIES[k % 8], label=m, edgecolor=SURFACE, linewidth=1)
        for x, v in zip(xs, vals):
            ax.text(x, v + 1.5, f"{v:.0f}%", ha="center", fontsize=7, color=INK2)
    ax.set_xticks([i + w * (len(models) - 1) / 2 for i in range(len(styles))]); ax.set_xticklabels(styles)
    ax.set_ylim(0, 110); ax.set_ylabel("Accuracy (%)")
    _style_axes(ax); ax.grid(axis="y", color=GRID, lw=0.8); ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("Same answer key, different image style", loc="left", fontsize=11, color=INK)
    fig.tight_layout(); fig.savefig(out / "chart_by_style.png", dpi=150); plt.close(fig)


def _pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def markdown(S, out):
    L = ["# ThirstMap evaluation report", ""]
    if any(m.startswith("mock:") for m in S["models"]):
        L += ["> **Note:** `mock:*` entries are offline baselines, not AI models: `oracle` returns the answer key "
              "(tests the scorer), `random` picks random options (chance level), `stubborn` repeats the original "
              "answer on counterfactual twins. Their numbers are expected by construction; see docs/VERIFICATION.md.", ""]
    L += ["## Overall", "", "| Model | With image | Without image (blind) | Tasks |", "|---|---|---|---|"]
    for m, v in S["overall"].items():
        L.append(f"| {m} | {_pct(v['image'])} | {_pct(v['blind'])} | {v['n']} |")
    L += ["", "## Accuracy by visual skill", "", "| Skill | " + " | ".join(S["models"]) + " |",
          "|---|" + "---|" * len(S["models"])]
    for sk in SKILL_ORDER:
        if any(sk in S["by_skill"][m] for m in S["models"]):
            L.append(f"| {SKILL_LABEL[sk]} | " + " | ".join(_pct(S["by_skill"][m].get(sk)) for m in S["models"]) + " |")
    L += ["", "## Eye exam: breaking level (first difficulty where accuracy < 50%)", "",
          "| Skill | " + " | ".join(S["models"]) + " |", "|---|" + "---|" * len(S["models"])]
    for sk in SKILL_ORDER:
        if any(sk in S["breaking_level"][m] for m in S["models"]):
            L.append(f"| {SKILL_LABEL[sk]} | " + " | ".join(str(S["breaking_level"][m].get(sk, "–")) for m in S["models"]) + " |")
    L += ["", "## Map vs satellite (same scene, same question)", "",
          "| Model | Pairs | Both right | Only map right | Only satellite right | Both wrong |", "|---|---|---|---|---|---|"]
    for m, v in S["map_vs_satellite"].items():
        L.append(f"| {m} | {v['n']} | {v['both_right']} | {v['only_map']} | {v['only_satellite']} | {v['both_wrong']} |")
    L += ["", "## Counterfactual pairs (one minimal change that must flip the answer)", "",
          "Pair accuracy counts a pair only if BOTH the original and its twin are answered correctly. "
          "'Unchanged answer' = the model gave the same answer to both, although the correct answer changed.", "",
          "| Model | Pairs | Single-task accuracy | Pair accuracy | Unchanged answer |", "|---|---|---|---|---|"]
    for m, v in S["counterfactual_pairs"].items():
        L.append(f"| {m} | {v['pairs']} | {_pct(v['single_task_accuracy'])} | {_pct(v['pair_accuracy'])} | "
                 f"{_pct(v['unchanged_answer_rate'])} |")
    L += ["", "## Traps and error diagnosis", "", "| Model | Trap tasks | Fell for a trap | Most common errors |", "|---|---|---|---|"]
    for m in S["models"]:
        t = S["trap_fall_rate"][m]
        top = ", ".join(f"{k} ({v})" for k, v in list(S["error_tags"][m].items())[:4])
        L.append(f"| {m} | {t['exposed']} | {_pct(t['rate'])} | {top or '–'} |")
    L += ["", f"Tasks a majority of real models answered correctly WITHOUT the image: "
          f"{len(S['tasks_guessable_without_image'])}", "",
          "## Cost", "", "| Model | Input tokens | Output tokens | USD | Mean latency (s) |", "|---|---|---|---|---|"]
    for m, c in S["cost"].items():
        L.append(f"| {m} | {c['input_tokens']} | {c['output_tokens']} | {c['usd']} | {c['mean_latency_s']} |")
    L += ["", "![skills](chart_accuracy_by_skill.png)", "", "![eye exam](chart_eye_exam.png)", "",
          "![styles](chart_by_style.png)", ""]
    (out / "REPORT.md").write_text("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--dataset", default="dataset")
    a = ap.parse_args()
    build_report(a.run_dir, a.dataset)
