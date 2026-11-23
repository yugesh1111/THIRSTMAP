"""Appearance variants: the SAME scene with the SAME answers, rendered the way real imagery varies.

  monsoon : wet season (greener vegetation, darker soil)
  haze    : dust / smog haze (lower contrast)
  coarse  : half the ground resolution (a cheaper sensor); labels stay crisp

A model that truly reads the landscape gives the same answer for every appearance. This is the
mirror image of the counterfactual twins (one small change that MUST flip the answer).

Usage: python3 variants.py --dataset dataset --per-level 6 --per-location 2
  -> dataset/variants/<scene>/<variant>.png and dataset/variants.jsonl
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from thirstmap import realterrain, render_sat
from thirstmap.questions import answer_key
from thirstmap.render_sat import _px
from thirstmap.scene import make
from thirstmap.terrain import params
from thirstmap.validate import label_overlaps, path_visibility
from verify_results import recover_jobs

VARIANTS = {"monsoon": dict(season="monsoon"), "haze": dict(haze=0.5), "coarse": dict(coarse=2)}


def rebuild(key, scene_name, ds):
    """Rebuild a published scene from its seed; confirm the answers match the dataset."""
    real = scene_name.split("_seed")[0][5:] if scene_name.startswith("real_") else None
    R = realterrain.load(real) if real else None
    P = params(key["level"])
    want = {q["id"]: q["answer"] for q in key["questions"]}
    for k, _ in recover_jobs(key):
        s, p = make(key["seed"], P, bi=k, real=R)
        qs, nm, truth = answer_key(s, p)
        got = {q["id"]: q["answer"] for q in qs}
        if all(got.get(q) == a for q, a in want.items()):
            return s, p, nm, P
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--per-level", type=int, default=6)
    ap.add_argument("--per-location", type=int, default=2)
    a = ap.parse_args()
    ds = Path(a.dataset)
    tasks = [json.loads(l) for l in open(ds / "tasks.jsonl")]
    sat = defaultdict(list)
    for t in tasks:
        if t["style"] == "satellite" and t.get("variant") != "counterfactual":
            sat[t["scene_id"]].append(t)
    rng = random.Random(3)
    pick = []
    for prefix, n in [(f"level{lv}_", a.per_level) for lv in range(1, 6)] + \
                     [(f"real_{loc}_", a.per_location) for loc in realterrain.LOCATIONS]:
        pool = sorted(s for s in sat if s.startswith(prefix))
        pick += rng.sample(pool, min(n, len(pool)))
    out, report = [], defaultdict(int)
    for scene in pick:
        key = json.loads((ds / "scenes" / scene / "answer_key.json").read_text())
        built = rebuild(key, scene, ds)
        if not built:
            report["could_not_rebuild"] += 1
            continue
        s, p, nm, P = built
        pos = {i: k for k, i in enumerate(s["path"])}
        hit = sorted([v for v in p["villages"] if v in pos], key=pos.get)
        cells = s["path"][2: (pos[hit[-1]] + 1) if hit else 40]
        folder = ds / "variants" / scene
        folder.mkdir(parents=True, exist_ok=True)
        for name, kw in VARIANTS.items():
            img = render_sat.render(s, p, nm, P, title=f"{key.get('scene_id', scene)} | satellite-style | "
                                    f"{name} | {s['drain_note'].lower()}", **kw)
            off = img.info["offset"]
            arr = np.asarray(img)
            vis = path_visibility("satellite", arr, lambda i: (_px(i)[0], _px(i)[1] + off), cells)
            bad = label_overlaps(img.info["labels"], (arr.shape[1], arr.shape[0]))
            if vis < 0.9 or bad:                       # evidence must survive the appearance change
                report[f"dropped_{name}"] += 1
                continue
            img.save(folder / f"{name}.png")
            report[f"kept_{name}"] += 1
            for t in sat[scene]:
                v = dict(t, task_id=f"{t['task_id']}__{name}", image=str((folder / f"{name}.png").relative_to(ds)),
                         appearance=name, group_id=t["task_id"])
                v.pop("pair_id", None); v.pop("variant", None)
                out.append(v)
    with open(ds / "variants.jsonl", "w") as f:
        for t in out:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"{len(pick)} scenes, {len(out)} variant tasks -> {ds / 'variants.jsonl'}; {dict(report)}")


if __name__ == "__main__":
    main()
