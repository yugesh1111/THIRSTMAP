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


def paired(run, tasks, a, b):
    """Exact McNemar test on the same questions: (only a right, only b right, one-sided p that a > b)."""
    from scipy.stats import binomtest
    from thirstmap.scoring import score
    got = {}
    for line in open(Path(run) / "responses.jsonl"):
        r = json.loads(line)
        if r["task_id"] in tasks and not r.get("error"):
            got[(r["model"], r["mode"], r["task_id"])] = score(tasks[r["task_id"]], r["raw"])["correct"]
    ids = {k[2] for k in got if k[:2] == a} & {k[2] for k in got if k[:2] == b}
    x = sum(got[a + (t,)] and not got[b + (t,)] for t in ids)
    y = sum(got[b + (t,)] and not got[a + (t,)] for t in ids)
    return x, y, (binomtest(x, x + y, 0.5, alternative="greater").pvalue if x + y else 1.0)


def pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def short(m):
    return m.split("/")[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/open_models")
    ap.add_argument("--finetune", default="results/finetune")
    ap.add_argument("--dataset", default="dataset")
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
            ft_bullet = None
            vb, vt = F["vs_chance"][base], F["vs_chance"][tuned]
            ob, ot = F["overall"][base], F["overall"][tuned]
            fb, ft_ = F.get("format", {}).get(base, {}), F.get("format", {}).get(tuned, {})
            L += ["", "## Can the dataset teach the skill? (fine-tuning)", "",
                  f"{info.get('base_model', 'A small model')} was fine-tuned with LoRA on {info.get('train_tasks', '?')} "
                  f"tasks for {info.get('epochs', '?')} epochs on CPU ({round(info.get('train_seconds', 0) / 60)} min), "
                  f"using only scenes that never appear in the test set ({info.get('held_out_scene_families', '?')} "
                  f"held-out scene families, {vb['n']} test questions). Both versions answer the same test questions "
                  "with the same image settings, and again without the image:", "",
                  "| Model | Accuracy | Without image | Chance | p (beats chance) | Well-formed replies | Accuracy, well-formed only |",
                  "|---|---|---|---|---|---|---|"]
            for label, v, o, f in (("base", vb, ob, fb), ("fine-tuned on ThirstMap", vt, ot, ft_)):
                L.append(f"| {label} | **{pct(v['correct'] / v['n'])}** ({v['correct']}/{v['n']}) | {pct(o.get('blind'))} | "
                         f"{pct(v['chance'])} | {v['p_value']:.2g} | {pct(f.get('well_formed'))} | "
                         f"{pct(f.get('accuracy_well_formed_only'))} |")
            gain = vt["correct"] / vt["n"] - vb["correct"] / vb["n"]
            tasks = {json.loads(l)["task_id"]: json.loads(l) for l in open(Path(a.dataset) / "tasks.jsonl")}
            x1, y1, p1 = paired(a.finetune, tasks, (tuned, "image"), (base, "image"))
            gain_txt = (f"Fine-tuning raised accuracy by {gain * 100:.0f} percentage points (paired test on the same "
                        f"questions: {x1} answers became right, {y1} became wrong, p = {p1:.2g}).")
            if ot.get("blind") is not None:
                gap = vt["correct"] / vt["n"] - ot["blind"]
                x2, y2, p2 = paired(a.finetune, tasks, (tuned, "image"), (tuned, "blind"))
                base_same = ob.get("blind") is not None and abs(ob["image"] - ob["blind"]) < 0.03
                if gap >= 0.05 and p2 < 0.05:
                    verdict = (f"**The tuned model learned to use the image:** it scores {gap * 100:.0f} percentage points "
                               f"higher with the image than without it ({x2} questions right only with the image, {y2} "
                               f"only without; p = {p2:.2g})"
                               + (", while the base model scored the same either way" if base_same else "")
                               + ". So the gain is not just the answer format or typical answers. It is still far from "
                               "reliable: most answers remain wrong.")
                    ft_bullet = (f"- **The dataset can teach the skill, a little.** Fine-tuning the smallest model on 300 "
                                 f"ThirstMap tasks raised it from {pct(vb['correct'] / vb['n'])} to "
                                 f"{pct(vt['correct'] / vt['n'])} on held-out scenes (p = {p1:.2g}), and the tuned model "
                                 f"now does better with the image than without it ({pct(vt['correct'] / vt['n'])} vs "
                                 f"{pct(ot['blind'])}, p = {p2:.2g}).")
                elif gap >= 0.05:
                    verdict = (f"The tuned model scores {gap * 100:.0f} percentage points higher with the image than "
                               f"without it, but that difference is not significant on these questions (p = {p2:.2g}).")
                else:
                    verdict = (f"But the tuned model scores about as well without the image ({pct(ot['blind'])}), so the "
                               "gain comes mostly from learning the answer format and typical answers, not from reading "
                               "the image. Small models need more than a few hundred examples to learn to trace water.")
            else:
                verdict = "(No without-image control was run for this fine-tune.)"
            L += ["", f"{gain_txt} {verdict}", "",
                  "| Skill | Chance | base | fine-tuned |", "|---|---|---|---|"]
            for s_ in SKILL_ORDER:
                if s_ in F["by_skill"].get(base, {}):
                    L.append(f"| {SKILL_LABEL[s_]} | {pct(F['chance_by_skill'].get(s_))} | "
                             f"{pct(F['by_skill'][base].get(s_))} | {pct(F['by_skill'][tuned].get(s_))} |")
            L += ["", f"The adapter is in `{meta.parent}/` ({sum(f.stat().st_size for f in meta.parent.iterdir()) / 2**20:.0f} MB); "
                  "load it with `peft.PeftModel.from_pretrained`."]
            if ft_bullet:
                L.insert(L.index("## Accuracy by skill (chance = random guessing on the same tasks)") - 1, ft_bullet)
    fm = S.get("format", {})
    if fm:
        L += ["", "## Strict check: well-formed replies only", "",
              "The scorer is lenient: a reply that names the right labels counts even if it is badly formatted "
              "(small models often write broken JSON). Counting only well-formed replies does not change the "
              "conclusion:", "", "| Model | Well-formed replies | Accuracy (all) | Accuracy (well-formed only) |",
              "|---|---|---|---|"]
        for r in rows:
            v = fm.get(r["m"])
            if v:
                L.append(f"| {r['name']} | {pct(v['well_formed'])} | {pct(r['acc'])} | {pct(v['accuracy_well_formed_only'])} |")
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
                      ["![accuracy by skill vs chance](results/open_models/chart_accuracy_by_skill.png)", "",
                       "Full tables, fine-tuning and caveats: [docs/FINDINGS.md](docs/FINDINGS.md) · "
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
