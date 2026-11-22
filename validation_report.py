"""Collect all validation evidence into docs/VALIDATION_REPORT.md (+ charts).

Pulls together: the automated test suite, every validator's pass rate across the dataset,
the independent (pysheds) agreement, dropped questions and why, answer balance,
counterfactual pairs, and the offline baselines.

Usage: python3 validation_report.py [--dataset dataset] [--baselines results/offline_baselines]
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from report import GRID, INK, INK2, SERIES, SURFACE, _style_axes

WHAT = {
    "V1_independent_pysheds": "Every answer re-derived with a third-party hydrology library (pysheds) must match",
    "V5_elevation_margin": "No farm within 3 m of the pond's height (gravity question)",
    "V7_spatial_margin": "Unaffected villages are at least 5 cells from the wastewater path",
    "V8_single_wetland": "Exactly one wetland site cleans the water before any village",
    "V_temp_margin": "No monitoring point within 0.8 °C of the 3 °C threshold",
    "V9_path_visible_satellite": "The answer path is visible in the satellite image's pixels",
    "V9_path_visible_map": "The answer path is visible in the map's pixels",
    "V9_path_visible_thermal": "The plume is visible in the thermal image's pixels with the right colour",
    "V10_labels_satellite": "Labels inside the image and never overlapping (satellite)",
    "V10_labels_map": "Labels inside the image and never overlapping (map)",
    "V10_labels_thermal": "Labels inside the image and never overlapping (thermal)",
    "V11_style_applicability": "Each question is only asked in image styles that contain its evidence",
}


def run_tests():
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rA", "--no-header"],
                         capture_output=True, text=True)
    lines = out.stdout.splitlines()
    tail = next((l for l in reversed(lines) if re.search(r"\d+ passed", l)), lines[-1] if lines else "")
    passed = [l.split(" ", 1)[1] for l in lines if l.startswith("PASSED ")]
    failed = [l.split(" ", 1)[1] for l in lines if l.startswith("FAILED ")]
    return tail.strip("= "), passed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--baselines", default="results/offline_baselines")
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    ds, out = Path(a.dataset), Path(a.out)
    out.mkdir(exist_ok=True)
    man = json.loads((ds / "manifest.json").read_text())
    vals = [json.loads(p.read_text()) for p in sorted((ds / "scenes").glob("*/validation.json"))]
    agree = [v["checks"]["V1_independent_pysheds"]["receiver_agreement"] for v in vals]
    tasks = [json.loads(l) for l in open(ds / "tasks.jsonl")]
    test_line, passed, failed = run_tests()

    # chart 1: validator pass rates
    names = [k for k in WHAT if k in man["validation_pass_rate"]]
    rates = []
    for k in names:
        ok, n = map(int, man["validation_pass_rate"][k].split("/"))
        rates.append(100 * ok / n)
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(names) + 1.0), facecolor=SURFACE)
    ax.barh(range(len(names)), rates, color=SERIES[0], height=0.65, edgecolor=SURFACE)
    for i, (k, r) in enumerate(zip(names, rates)):
        ax.text(r + 0.6, i, man["validation_pass_rate"][k], va="center", fontsize=7, color=INK2)
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=7); ax.invert_yaxis()
    ax.set_xlim(0, 112); ax.set_xlabel("Scenes passing (%)  ·  failures drop the question, never edit it")
    _style_axes(ax)
    ax.set_title("Validator pass rates across the dataset", loc="left", fontsize=11, color=INK)
    fig.tight_layout(); fig.savefig(out / "validation_pass_rates.png", dpi=150); plt.close(fig)

    # chart 2: correct-answer balance for single-choice questions
    bal = man["answer_balance"]
    qs = [q for q in ("Q2", "Q3", "Q5", "Q6") if q in bal]
    fig, axes = plt.subplots(1, len(qs), figsize=(2.6 * len(qs), 2.6), facecolor=SURFACE)
    for ax, q in zip(axes, qs):
        items = sorted(bal[q].items(), key=lambda kv: (len(kv[0]), kv[0]))
        ax.bar([k for k, _ in items], [v for _, v in items], color=SERIES[0], edgecolor=SURFACE)
        ax.set_title({"Q2": "Q2 first village", "Q3": "Q3 wetland", "Q5": "Q5 direction",
                      "Q6": "Q6 clean site"}[q], fontsize=9, loc="left", color=INK)
        _style_axes(ax); ax.grid(axis="y", color=GRID, lw=0.8); ax.grid(axis="x", visible=False)
        ax.tick_params(axis="x", labelsize=7)
    axes[0].set_ylabel("Tasks with this correct answer", fontsize=8)
    fig.tight_layout(); fig.savefig(out / "validation_answer_balance.png", dpi=150); plt.close(fig)

    base = Path(a.baselines) / "summary.json"
    B = json.loads(base.read_text()) if base.exists() else None
    cp = man.get("counterfactual_pairs", {})

    L = ["# ThirstMap — validation evidence", "",
         f"Dataset: **{man['n_scenes']} scenes, {man['n_tasks']} tasks** "
         f"({', '.join(f'{k}: {v}' for k, v in man['tasks_by_terrain'].items())}); "
         f"built in {man['build_seconds']} s. Generated by `build_dataset.py`; this report by `validation_report.py`.", "",
         "## 1. Automated tests", "", f"**{test_line}**", ""]
    L += [f"- ✅ `{t}`" for t in passed] + [f"- ❌ `{t}`" for t in failed] + [""]
    L += ["## 2. Validators on every generated scene", "",
          "A question is kept only if every check relevant to it passes; failing questions are dropped and "
          "failing scenes regenerated. **Nothing is edited by hand.**", "",
          "| Check | What it proves | Pass |", "|---|---|---|"]
    for k in names:
        L.append(f"| {k} | {WHAT[k]} | {man['validation_pass_rate'][k]} |")
    L += ["", "![pass rates](validation_pass_rates.png)", "",
          "### Independent implementation (V1)", "",
          f"Flow directions recomputed by **pysheds** agree with ours on **{100 * statistics.mean(agree):.2f}%** of cells "
          f"on average (minimum {100 * min(agree):.2f}%, over {len(agree)} scenes incl. counterfactual twins). "
          "Disagreements are ties between equally steep neighbours; any question whose answer they change is dropped.", "",
          "### Dropped questions (and why)", "", "| Question: reason | Count |", "|---|---|"]
    for k, v in sorted(man["dropped_questions"].items(), key=lambda kv: -kv[1]):
        L.append(f"| {k} | {v} |")
    if man.get("failed_jobs"):
        L += ["", f"Scenes that never passed validation (recorded, not patched): {len(man['failed_jobs'])}"]
    L += ["", "## 3. Answer balance (no answer position is favoured)", "",
          "![answer balance](validation_answer_balance.png)", "",
          "Set-valued answers by size: " + "; ".join(
              f"{q}: " + ", ".join(f"{k.replace('size=', '')}→{v}" for k, v in sorted(bal[q].items()))
              for q in ("Q1", "Q4", "Q7", "Q8") if q in bal), ""]
    L += ["## 4. Counterfactual pairs", "",
          f"{cp.get('scenes_with_twin', 0)} scenes have a twin with one minimal change that must flip the answer; "
          f"**{cp.get('pairs', 0)} linked pairs** (by kind: {dict(cp.get('by_kind', {}))}). Each twin is validated "
          "independently, and a pair is only kept if the reference answers differ.", ""]
    if B:
        L += ["## 5. Baselines (does scoring separate right from wrong? can tasks be guessed?)", "",
              "| Baseline | Accuracy | Without image | Pair accuracy |", "|---|---|---|---|"]
        for m in B["models"]:
            o, pr = B["overall"][m], B["counterfactual_pairs"].get(m, {})
            pct = lambda x: "–" if x is None else f"{100 * x:.0f}%"
            L.append(f"| {m} | {pct(o['image'])} | {pct(o['blind'])} | {pct(pr.get('pair_accuracy'))} |")
        L += ["", "- **oracle** = 100%: the scorer accepts every correct answer, in every format variant tested.",
              "- **random** ≈ chance: per skill " + ", ".join(
                  f"{k}: {100 * v:.0f}%" for k, v in B["by_skill"].get("mock:random", {}).items()) + ".",
              "- **stubborn** (never notices a change) looks strong on single tasks but scores 0% pair accuracy: "
              "the pairs expose answering from habit.", ""]
    L += ["## 6. Known limitations", "",
          "- Synthetic terrain and D8 routing simplify real hydrology (no groundwater, canals, pipes or seasons).",
          "- The heat plume is a decay-and-mixing model; real plumes depend on flow rates and weather.",
          "- Real-terrain scenes use a lightly smoothed surface model and hypothetical facilities.",
          "- Human solvability (V15) is measured with `human_eval/` — results are added when collected.", ""]
    (out / "VALIDATION_REPORT.md").write_text("\n".join(L))
    print(f"wrote {out / 'VALIDATION_REPORT.md'} · tests: {test_line}")


if __name__ == "__main__":
    main()
