"""Evaluate models on the benchmark.

Usage:
  python3 evaluate.py --dataset dataset --models mock:oracle mock:random --run offline_check
  python3 evaluate.py --dataset dataset --models claude:claude-opus-5-5 --per-cell 3 --blind --run opus55

--per-cell N samples up to N tasks per (question, style, difficulty) cell, so a run covers every
skill x style x level at a predictable cost. Responses are appended to results/<run>/responses.jsonl
and an interrupted run resumes where it stopped.
"""
import argparse
import json
import random
import threading
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from report import build_report
from thirstmap.models import cost_usd, make_adapter
from thirstmap.scoring import score


def load_tasks(dataset, per_cell=None, levels=None, styles=None, seed=0, pairs=0, probes=0, variants=0):
    """Pick the tasks for a run.

    per_cell : up to N original tasks per (question, style, difficulty) cell
    pairs    : N complete counterfactual pairs (original + twin), balanced across twin kinds
    probes   : N perception-probe tasks per (probe, style) from probes.jsonl ("can it read the labels?")
    variants : N appearance groups (original satellite task + monsoon / haze / coarse versions)
    """
    ds = Path(dataset)
    tasks = [json.loads(l) for l in open(ds / "tasks.jsonl")]
    tasks = [t for t in tasks if (not levels or t["level"] in levels) and (not styles or t["style"] in styles)]
    rng = random.Random(seed)
    if not (per_cell or pairs or probes or variants):
        return tasks
    chosen = []
    if per_cell:
        cells = defaultdict(list)
        for t in tasks:
            if t.get("variant") != "counterfactual":
                cells[(t["qid"], t["style"], t["level"])].append(t)
        chosen += [t for k in sorted(cells) for t in rng.sample(cells[k], min(per_cell, len(cells[k])))]
    if pairs:
        by_pair = defaultdict(dict)
        for t in tasks:
            if t.get("pair_id"):
                by_pair[t["pair_id"]][t["variant"]] = t
        by_kind = defaultdict(list)
        for pid, v in sorted(by_pair.items()):
            if len(v) == 2:
                by_kind[v["counterfactual"]["cf_kind"]].append(v)
        kinds = sorted(by_kind)
        picked, k = [], 0
        while len(picked) < pairs and any(by_kind.values()):
            pool = by_kind[kinds[k % len(kinds)]]
            if pool:
                picked.append(pool.pop(rng.randrange(len(pool))))
            k += 1
        have = {t["task_id"] for t in chosen}
        chosen += [t for v in picked for t in (v["base"], v["counterfactual"]) if t["task_id"] not in have]
    if probes and (ds / "probes.jsonl").exists():
        cells = defaultdict(list)
        for line in open(ds / "probes.jsonl"):
            t = json.loads(line)
            cells[(t["qid"], t["style"])].append(t)
        chosen += [t for k in sorted(cells) for t in rng.sample(cells[k], min(probes, len(cells[k])))]
    if variants and (ds / "variants.jsonl").exists():
        groups = defaultdict(list)
        for line in open(ds / "variants.jsonl"):
            t = json.loads(line)
            groups[t["group_id"]].append(t)
        base = {t["task_id"]: t for t in tasks}
        by_q = defaultdict(list)
        for gid in sorted(groups):
            if gid in base:
                by_q[base[gid]["qid"]].append(gid)
        picked, k = [], 0
        qs = sorted(by_q)
        while len(picked) < variants and any(by_q.values()):
            pool = by_q[qs[k % len(qs)]]
            if pool:
                picked.append(pool.pop(rng.randrange(len(pool))))
            k += 1
        have = {t["task_id"] for t in chosen}
        for gid in picked:
            for t in [base[gid]] + groups[gid]:
                if t["task_id"] not in have:
                    chosen.append(t); have.add(t["task_id"])
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--per-cell", type=int, default=None)
    ap.add_argument("--levels", type=int, nargs="*")
    ap.add_argument("--styles", nargs="*")
    ap.add_argument("--blind", action="store_true", help="also ask every question WITHOUT the image")
    ap.add_argument("--workers", type=int, default=4, help="parallel calls (use 1 for local hf: models)")
    ap.add_argument("--pairs", type=int, default=0, help="also include N complete counterfactual pairs")
    ap.add_argument("--probes", type=int, default=0, help="also include N perception probes per (probe, style)")
    ap.add_argument("--variants", type=int, default=0, help="also include N appearance groups (4 looks each)")
    a = ap.parse_args()

    root = Path(a.dataset).resolve()          # task image paths are relative to the dataset folder
    tasks = load_tasks(a.dataset, a.per_cell, a.levels, a.styles, pairs=a.pairs, probes=a.probes,
                       variants=a.variants)
    out = Path("results") / a.run
    out.mkdir(parents=True, exist_ok=True)
    resp_path = out / "responses.jsonl"
    done = set()
    if resp_path.exists():
        for line in open(resp_path):
            r = json.loads(line)
            if not r.get("error"):
                done.add((r["model"], r["mode"], r["task_id"]))
    lock = threading.Lock()
    modes = ["image", "blind"] if a.blind else ["image"]
    adapters = [make_adapter(m, root=root) for m in a.models]
    jobs = [(ad, mode, t) for ad in adapters for mode in modes for t in tasks
            if (ad.name, mode, t["task_id"]) not in done]
    print(f"{len(tasks)} tasks x {len(adapters)} models x {len(modes)} modes -> {len(jobs)} calls to make")

    def run(ad, mode, t):
        rec = dict(model=ad.name, mode=mode, task_id=t["task_id"])
        try:
            r = ad.ask(t, with_image=(mode == "image"))
            rec.update(r)
            rec.update(score(t, r["raw"]))
            rec["cost_usd"] = cost_usd(ad.name, r.get("input_tokens"), r.get("output_tokens"))
        except Exception as e:                       # recorded, retried on the next run
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["trace"] = traceback.format_exc(limit=2)
        with lock, open(resp_path, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        return rec

    n_err = 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(run, *j) for j in jobs]
        for k, fu in enumerate(as_completed(futs), 1):
            n_err += bool(fu.result().get("error"))
            if k % 50 == 0 or k == len(futs):
                print(f"  {k}/{len(futs)} done, {n_err} errors")
    (out / "run_config.json").write_text(json.dumps(vars(a), indent=2))
    build_report(out, Path(a.dataset))


if __name__ == "__main__":
    main()
