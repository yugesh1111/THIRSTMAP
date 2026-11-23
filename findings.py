"""Write docs/FINDINGS.md and the README findings block straight from the computed results.

Every number comes from results/<run>/summary.json (and results/finetune/ if present),
so nothing is copied by hand.

Usage: python3 findings.py --run results/open_models [--finetune results/finetune]
"""
import argparse
import json
import re
from pathlib import Path

from report import SKILL_LABEL, SKILL_ORDER

SIZE = {"Qwen2.5-VL-3B-Instruct": "3B", "Qwen2-VL-2B-Instruct": "2B", "SmolVLM2-2.2B-Instruct": "2.2B",
        "SmolVLM-256M-Instruct": "0.26B"}


def pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def short(m):
    return m.split("/")[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/open_models")
    ap.add_argument("--finetune", default="results/finetune")
    a = ap.parse_args()
    S = json.loads((Path(a.run) / "summary.json").read_text())
    models = [m for m in S["models"] if m.startswith("hf:")]
    rows = []
    for m in models:
        vc = S["vs_chance"].get(m)
        if not vc:
            continue
        pr = S["counterfactual_pairs"].get(m, {})
        inv = S.get("appearance_invariance", {}).get(m, {})
        probes = S.get("perception_probes", {}).get(m, {})
        lab = list(probes.values())
        read = sum(v["acc"] * v["n"] for v in lab) / sum(v["n"] for v in lab) if lab else None
        read_n = sum(v["n"] for v in lab)
        rows.append(dict(m=m, name=short(m), size=SIZE.get(short(m), "?"), acc=vc["correct"] / vc["n"],
                         n=vc["n"], chance=vc["chance"], p=vc["p_value"], blind=S["overall"][m]["blind"],
                         pair=pr.get("pair_accuracy"), same=pr.get("unchanged_answer_rate"),
                         inv=inv.get("same_answer_all_looks"), inv_n=inv.get("groups"), read=read,
                         read_n=read_n if lab else 0))
    rows.sort(key=lambda r: -r["acc"])
    L = ["# Findings: how well do open vision-language models trace water through the landscape?", "",
         "Free, open-weight models from Hugging Face, run locally on CPU (no API keys). Every model answered the "
         "**same tasks**: one per (question × image style × difficulty) cell, 30 counterfactual pairs, perception "
         "probes, and every question again **without the image**. Frontier API models (Claude, GPT, Gemini) run with "
         "the same harness once keys are available.", "",
         "| Model | Size | Accuracy | Without image | Chance | p (beats chance) | Pair accuracy | Same answer to original & twin | Same answer in 4 looks | Reading checks |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        inv_n = f" (n={r['inv_n']})" if r["inv_n"] else ""
        L.append(f"| {r['name']} | {r['size']} | **{pct(r['acc'])}** ({round(r['acc'] * r['n'])}/{r['n']}) | "
                 f"{pct(r['blind'])} | {pct(r['chance'])} | {r['p']:.2g} | {pct(r['pair'])} | {pct(r['same'])} | "
                 f"{pct(r['inv'])}{inv_n} | {pct(r['read'])}{f" (n={r['read_n']})" if r['read_n'] else ''} |")
    full = max(r["n"] for r in rows)
    partial = [r for r in rows if r["n"] < full]
    if partial:
        L += ["", "*Interim: evaluation still running for " + ", ".join(
            f"{r['name']} ({r['n']} of {full} tasks so far)" for r in partial)
              + "; numbers for it will change and more models may be added.*"]
    beats = [r for r in rows if r["p"] < 0.05]
    L += ["", "## What the numbers say", ""]
    if not beats:
        L.append(f"- **No open model is significantly better than random guessing overall** (all p ≥ 0.05). "
                 f"The best, {rows[0]['name']}, scores {pct(rows[0]['acc'])} against a chance level of "
                 f"{pct(rows[0]['chance'])} (p = {rows[0]['p']:.2g}).")
    else:
        L.append("- Better than chance (p < 0.05): " + ", ".join(f"{r['name']} ({pct(r['acc'])} vs {pct(r['chance'])})"
                                                              for r in beats) + ".")
    withb = [r for r in rows if r["blind"] is not None]
    if withb:
        gap = max(r["acc"] - r["blind"] for r in withb)
        head = ("The image barely helps." if gap < 0.10 else "The image helps some models.")
        L.append(f"- **{head}** Accuracy with vs without the image: "
                 + "; ".join(f"{r['name']} {pct(r['acc'])} vs {pct(r['blind'])}" for r in withb) + ".")
    same = [r for r in rows if r["same"] is not None]
    if same:
        head = ("Counterfactual twins expose answering from habit."
                if max(r["same"] for r in same) >= 0.5 else "Models mostly notice the counterfactual change.")
        L.append(f"- **{head}** Share of pairs where the model gave the same answer to the original and to its "
                 "twin (whose correct answer is different): "
                 + "; ".join(f"{r['name']} {pct(r['same'])} (both right: {pct(r['pair'])})" for r in same) + ".")
    inv = [r for r in rows if r["inv"] is not None]
    if inv:
        head = ("Appearance changes move answers." if min(r["inv"] for r in inv) < 0.9
                else "Answers are stable across appearance changes.")
        L.append(f"- **{head}** Share of question groups answered identically in the dry-season, monsoon, haze and "
                 "coarse-sensor versions of the same scene (the correct answer is identical in all four): "
                 + "; ".join(f"{r['name']} {pct(r['inv'])}" for r in inv) + ".")
    rd = [r for r in rows if r["read"] is not None]
    if rd:
        L.append("- **Can they read the image at all?** Reading checks need no reasoning: list every village or "
                 "monitoring-point label written on the image, or read the spot height printed next to pond P: " + "; ".join(f"{r['name']} {pct(r['read'])}" for r in rd)
                 + ". A model that reads labels but fails the water questions is failing the reasoning, not the eyesight.")
    # per-skill: where each model is clearly above / at / below chance
    by = S["by_skill"]
    ch = S["chance_by_skill"]
    best = max(rows, key=lambda r: r["acc"])["m"]
    above = [SKILL_LABEL[s] for s in SKILL_ORDER if s in by.get(best, {}) and by[best][s] >= ch[s] + 0.10]
    zero = [SKILL_LABEL[s] for s in SKILL_ORDER if s in by.get(best, {}) and by[best][s] == 0]
    L.append(f"- **Skill profile of the best model ({short(best)}):** clearly above chance on "
             f"{', '.join(above) or 'no skill'}; **0% on {', '.join(zero) or 'no skill'}**.")
    L += ["", "## Accuracy by skill (chance = random guessing on the same tasks)", "",
          "| Skill | Tasks | Chance | " + " | ".join(r["name"] for r in rows) + " |",
          "|---|---|---|" + "---|" * len(rows)]
    for s in SKILL_ORDER:
        if s in ch:
            L.append(f"| {SKILL_LABEL[s]} | {S['tasks_by_skill_evaluated'].get(s, 0)} | {pct(ch[s])} | "
                     + " | ".join(pct(by.get(r["m"], {}).get(s)) for r in rows) + " |")
    ft = Path(a.finetune) / "summary.json"
    if ft.exists():
        F = json.loads(ft.read_text())
        base = next((m for m in F["models"] if "(base)" in m), None)
        tuned = next((m for m in F["models"] if "fine-tuned" in m), None)
        meta = next(iter(Path("models").glob("*thirstmap-lora/TRAINING.json")), None)
        info = json.loads(meta.read_text()) if meta else {}
        if base and tuned:
            vb, vt = F["vs_chance"][base], F["vs_chance"][tuned]
            L += ["", "## Can the dataset teach the skill? (fine-tuning)", "",
                  f"{info.get('base_model', 'A small model')} was fine-tuned with LoRA on {info.get('train_tasks', '?')} "
                  f"tasks for {info.get('epochs', '?')} epoch(s) on CPU, using only scenes that never appear in the "
                  f"test set ({info.get('held_out_scene_families', '?')} held-out scene families). Same test tasks and image "
                  f"settings for both:", "",
                  "| Model | Accuracy | Chance | p (beats chance) |", "|---|---|---|---|",
                  f"| base | {pct(vb['correct'] / vb['n'])} ({vb['correct']}/{vb['n']}) | {pct(vb['chance'])} | {vb['p_value']:.2g} |",
                  f"| fine-tuned on ThirstMap | {pct(vt['correct'] / vt['n'])} ({vt['correct']}/{vt['n']}) | "
                  f"{pct(vt['chance'])} | {vt['p_value']:.2g} |", "",
                  "| Skill | base | fine-tuned |", "|---|---|---|"]
            for s in SKILL_ORDER:
                if s in F["by_skill"].get(base, {}):
                    L.append(f"| {SKILL_LABEL[s]} | {pct(F['by_skill'][base].get(s))} | {pct(F['by_skill'][tuned].get(s))} |")
    L += ["", "## Caveats", "",
          "- These are small open models (0.26B–3B parameters) on CPU, not frontier systems.",
          "- About 10–30 tasks per skill per model: per-skill differences of a few points are noise; "
          "the overall test against chance uses all tasks.",
          "- Images are synthetic renders; the real-terrain subset uses real elevation and land cover with hypothetical facilities.",
          "- Exact inputs are published in `eval_set/` so the run can be repeated on identical images."]
    Path("docs").mkdir(exist_ok=True)
    Path("docs/FINDINGS.md").write_text("\n".join(L) + "\n")
    readme = Path("README.md")
    s = readme.read_text()
    block = "\n".join(["<!-- FINDINGS:START -->", "## Findings (open models, real runs)", ""] +
                      [x.replace("## ", "### ", 1) if x.startswith("## ") else x for x in L[L.index("| Model | Size | Accuracy | Without image | Chance | p (beats chance) | Pair accuracy | Same answer to original & twin | Same answer in 4 looks | Reading checks |"):
                        L.index("## Accuracy by skill (chance = random guessing on the same tasks)")]] +
                      ["Full tables, fine-tuning and caveats: [docs/FINDINGS.md](docs/FINDINGS.md) · "
                       "per-run report: [results/open_models/REPORT.md](results/open_models/REPORT.md)",
                       "<!-- FINDINGS:END -->"])
    if "<!-- FINDINGS:START -->" in s:
        s = re.sub(r"<!-- FINDINGS:START -->.*?<!-- FINDINGS:END -->", lambda _: block, s, flags=re.S)
    else:
        s = s.replace("## See it", block + "\n\n## See it", 1)
    readme.write_text(s)
    print("\n".join(L[:20]))


if __name__ == "__main__":
    main()
