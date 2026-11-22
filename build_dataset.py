"""Build the benchmark: many validated scenes across difficulty levels -> tasks.jsonl + manifest.

Usage: python3 build_dataset.py --per-level 20 --levels 1 2 3 4 5 --out dataset --workers 4
"""
import argparse
import json
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from generate import generate
from thirstmap.dataset import tasks_for_scene

BASE_SEED = 1000


def one(job):
    level, k, out, real = job
    t0 = time.time()
    try:
        folder, kept, report = generate(level, BASE_SEED + 97 * k + 10007 * level, out, bi=k, real=real)
    except RuntimeError as e:                 # no valid scene: recorded, never patched by hand
        return dict(scene=None, level=level, real=real, error=str(e), tasks=[], report=None, seconds=time.time() - t0)
    key = json.loads((folder / "answer_key.json").read_text())
    styles = {st for q in kept for st in q["styles"]}
    rel = lambda name: str((folder / name).relative_to(Path(out).parent))
    tasks = tasks_for_scene(folder.name, level, kept,
                            {st: rel(f"{st}.png") for st in styles},
                            {st: rel(f"{st}_reveal.png") for st in styles},
                            drain=key["drain_note"], terrain=key["terrain"])
    return dict(scene=folder.name, level=level, tasks=tasks, report=report, seconds=time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=20)
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--out", default="dataset")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--real-per-location", type=int, default=0,
                    help="also build scenes on real terrain (Navi Mumbai, Hyderabad) at difficulty 3")
    a = ap.parse_args()

    root = Path(a.out)
    scenes_dir = root / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(lv, k, str(scenes_dir), None) for lv in a.levels for k in range(a.per_level)]
    jobs += [(3, k, str(scenes_dir), loc) for loc in ("navi_mumbai", "hyderabad")
             for k in range(a.real_per_location)]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        results = list(ex.map(one, jobs))

    failed = [dict(level=r["level"], real=r.get("real"), error=r["error"]) for r in results if r.get("error")]
    results = [r for r in results if not r.get("error")]
    tasks = [t for r in results for t in r["tasks"]]
    with open(root / "tasks.jsonl", "w") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    # ---- manifest: counts, validation summary, answer balance (V14)
    check_pass = defaultdict(lambda: [0, 0])
    drops = Counter()
    for r in results:
        for name, c in r["report"]["checks"].items():
            check_pass[name][0] += bool(c["passed"])
            check_pass[name][1] += 1
        for q, why in r["report"]["drop"].items():
            drops[f"{q}: {why}"] += 1
    balance = defaultdict(Counter)
    for t in tasks:
        if t["scoring"] in ("choice", "compass"):
            balance[t["qid"]][t["answer"]] += 1
        elif t["scoring"] == "set":
            balance[t["qid"]][f"size={len(t['answer'])}"] += 1
    manifest = dict(
        n_scenes=len(results), n_tasks=len(tasks), failed_jobs=failed,
        build_seconds=round(time.time() - t0, 1),
        tasks_by_level=Counter(t["level"] for t in tasks),
        tasks_by_terrain=Counter(t["terrain"] for t in tasks),
        tasks_by_style=Counter(t["style"] for t in tasks),
        tasks_by_skill=Counter(t["skill"] for t in tasks),
        validation_pass_rate={k: f"{v[0]}/{v[1]}" for k, v in sorted(check_pass.items())},
        dropped_questions=dict(drops),
        answer_balance={k: dict(v) for k, v in balance.items()},
    )
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    main()
