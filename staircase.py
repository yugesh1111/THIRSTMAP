"""Adaptive "eye exam": find each model's breaking level per skill with few API calls.

Like an optometrist's chart: start at difficulty 3. Two correct answers in a row make the
next task harder; one wrong answer makes it easier (the 2-down/1-up rule from vision
science, Levitt 1971). It converges where the model is right ~71% of the time, so lucky
guessing on multiple-choice questions cannot climb. The estimate is the mean level over
the last reversals (where the direction changes).

Usage:
  python3 staircase.py --dataset dataset --models claude:claude-opus-5-5 --trials 12 --run opus_eye
  python3 staircase.py --dataset dataset --models mock:oracle mock:random --run eye_offline
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from report import SKILL_LABEL, SKILL_ORDER
from thirstmap.models import cost_usd, make_adapter
from thirstmap.scoring import score

PREFERRED_STYLE = ["satellite", "map", "thermal"]


def staircase(adapter, pool, trials, rng):
    """pool: {level: [tasks]} for one skill. Returns trial log and threshold estimate."""
    level, log, last_dir, reversals, streak = 3, [], None, [], 0
    used = set()
    for _ in range(trials):
        cands = [t for t in pool.get(level, []) if t["task_id"] not in used]
        if not cands:
            break
        t = rng.choice(cands)
        used.add(t["task_id"])
        r = adapter.ask(t, with_image=True)
        s = score(t, r["raw"])
        log.append(dict(level=level, task_id=t["task_id"], correct=s["correct"], parsed=s["parsed"],
                        cost_usd=cost_usd(adapter.name, r.get("input_tokens"), r.get("output_tokens"))))
        if s["correct"]:
            streak += 1
            step = 1 if streak == 2 else 0
        else:
            step = -1
        if step:
            streak = 0
            if last_dir is not None and step != last_dir:
                reversals.append(level)
            last_dir = step
            level = min(5, max(1, level + step))
    if reversals:
        est = sum(reversals[-4:]) / len(reversals[-4:])
    elif log and all(x["correct"] for x in log):
        est = 5.5                                    # never failed: beyond the hardest level
    else:
        est = 0.5                                    # never succeeded: below the easiest level
    return dict(threshold=round(est, 2), trials=log, reversals=reversals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    ds = Path(a.dataset)
    tasks = [json.loads(l) for l in open(ds / "tasks.jsonl")]
    tasks = [t for t in tasks if t.get("variant") != "counterfactual" and t["terrain"] == "synthetic"]
    pools = defaultdict(lambda: defaultdict(list))
    for sk in SKILL_ORDER:
        styles = {t["style"] for t in tasks if t["skill"] == sk}
        style = next((s for s in PREFERRED_STYLE if s in styles), None)
        for t in tasks:
            if t["skill"] == sk and t["style"] == style:
                pools[sk][t["level"]].append(t)
    out = Path("results") / a.run
    out.mkdir(parents=True, exist_ok=True)
    res = {}
    for m in a.models:
        ad = make_adapter(m, root=ds.resolve())
        res[ad.name] = {sk: staircase(ad, pools[sk], a.trials, random.Random(hash((m, sk)) & 0xFFFF))
                        for sk in SKILL_ORDER if sk in pools}
    (out / "staircase.json").write_text(json.dumps(res, indent=2, default=str))
    L = ["# Adaptive eye exam (staircase)", "",
         f"{a.trials} trials per skill per model; estimate = mean difficulty level at the last reversals "
         "(0.5 = fails even level 1, 5.5 = never failed).", "",
         "| Skill | " + " | ".join(res) + " |", "|---|" + "---|" * len(res)]
    for sk in SKILL_ORDER:
        if any(sk in v for v in res.values()):
            L.append(f"| {SKILL_LABEL[sk]} | " + " | ".join(str(res[m][sk]["threshold"]) for m in res) + " |")
    calls = {m: sum(len(v["trials"]) for v in res[m].values()) for m in res}
    L += ["", "Calls used: " + ", ".join(f"{m}: {c}" for m, c in calls.items())]
    (out / "EYE_EXAM.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
