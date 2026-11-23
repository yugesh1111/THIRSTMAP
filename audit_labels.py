"""Audit of an existing dataset (docs/AUDIT.md), two checks:

  V10b   is any option label hidden under the scale bar, north arrow or colour legend?
  count  does a scene hold more villages / monitoring points / farms / wetlands than its design allows?
         (dataset v1.0 generator bug: a request for zero items filled every free site; fixed in checks v2)


Dataset v1.0 was built before check V10b. This script rebuilds every scene from its seed, re-renders each image
style exactly as it was built (and confirms the pixels match the published image), and lists every task with an
option label under an area drawn over the map. Those tasks go to <dataset>/errata.jsonl; every report, the
evaluator, the demo and the human test leave them out. New builds run V10b during generation.

Usage: python3 audit_labels.py --dataset dataset --workers 4      (re-renders every image; ~15 min on 4 cores)
       python3 audit_labels.py --reuse-cache                       (re-assembles from dataset/audit_cache.json)
"""
import argparse
import json
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from thirstmap import realterrain, render_map, render_sat, render_thermal  # noqa: E402
from thirstmap.rebuild import rebuild  # noqa: E402
from thirstmap.terrain import CELL_M, N  # noqa: E402
from thirstmap.validate import label_occlusions  # noqa: E402

DS = None


def title(key, s):
    km = N * CELL_M / 1000
    terr = key.get("terrain", "synthetic")
    tag = (f"Region TM-{key['seed']:05d} | difficulty {key['level']}/5 | {km:.0f} km x {km:.0f} km"
           if terr == "synthetic" else
           f"{realterrain.LOCATIONS[terr][2]} | hypothetical facility | {km:.0f} km x {km:.0f} km")
    return tag + (" | counterfactual twin" if key.get("pair_of") else "")


def audit_scene(scene_id):
    folder = DS / "scenes" / scene_id
    try:
        r = rebuild(DS, scene_id)
    except Exception as e:                                       # noqa: BLE001
        return scene_id, {"error": f"rebuild: {e}"}
    s, p, nm, P, key = r["s"], r["p"], r["nm"], r["P"], r["key"]
    tag = title(key, s)
    out = {}
    for style in ("satellite", "map", "thermal"):
        png = folder / f"{style}.png"
        if not png.exists():
            continue
        if style == "satellite":
            im = render_sat.render(s, p, nm, P, title=f"{tag} | satellite-style | {s['drain_note'].lower()}")
            labels, reserved, arr = im.info["labels"], im.info["reserved"], np.asarray(im.convert("RGB"))
        elif style == "thermal":
            im = render_thermal.render(s, p, nm, P, title=f"{tag} | thermal: water temperature above normal")
            labels, reserved, arr = im.info["labels"], im.info["reserved"], np.asarray(im.convert("RGB"))
        else:
            fig = render_map.render(s, p, nm, P, title=f"{tag} | topographic map")
            labels, reserved = fig.tm_labels, fig.tm_reserved
            arr = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
            plt.close(fig)
        same = np.array_equal(arr, np.asarray(Image.open(png).convert("RGB")))
        out[style] = dict(hidden=sorted(label_occlusions(labels, reserved)), pixel_identical=bool(same))
    return scene_id, out


def main():
    global DS
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--reuse-cache", action="store_true")
    a = ap.parse_args()
    DS = Path(a.dataset)
    cache = DS / "audit_cache.json"
    if a.reuse_cache and cache.exists():
        res = json.loads(cache.read_text())
    else:
        scenes = sorted(p.name for p in (DS / "scenes").iterdir() if (p / "answer_key.json").exists())
        with Pool(a.workers) as pool:
            res = dict(pool.imap_unordered(audit_scene, scenes, chunksize=4))
        cache.write_text(json.dumps(res, indent=0))
    tasks = [json.loads(l) for l in open(DS / "tasks.jsonl")]
    # count check: a whole scene (and its twin) is out if any question shows more items than the design allows
    design = {"Q1": lambda lv: 3 + lv, "Q2": lambda lv: 3 + lv, "Q7": lambda lv: 3 + lv,
              "Q4": lambda lv: min(6, 2 + lv), "Q3": lambda lv: 4, "Q8": lambda lv: 4, "Q6": lambda lv: 3}
    over = {}
    for t in tasks:
        lim = design.get(t["qid"])
        n = len(t.get("options") or [])
        if lim and n > lim(t["level"]):
            over[t["scene_id"].removesuffix("_cf")] = f"{n} options for {t['qid']} (design: {lim(t['level'])})"
    errata, per_style, examples = [], Counter(), defaultdict(list)
    count_out = []
    for t in tasks:
        base = t["scene_id"].removesuffix("_cf")
        if base in over:
            errata.append(dict(task_id=t["task_id"], check="count", reason="scene generator bug (fixed in checks v2): "
                               f"a request for zero items filled every free site; this scene has {over[base]}"))
            count_out.append(t["task_id"])
            continue
        info = res.get(t["scene_id"], {}).get(t["style"])
        if not info:
            continue
        hit = sorted(set(info["hidden"]) & {str(o) for o in (t.get("options") or [])})
        if hit:
            errata.append(dict(task_id=t["task_id"], check="V10b", hidden_labels=hit,
                               answer_hidden=bool(set(hit) & ({str(x) for x in t["answer"]} if isinstance(t["answer"], list)
                                                              else {str(t["answer"])})),
                               reason="an option label is drawn under the scale bar, north arrow or colour legend"))
            per_style[t["style"]] += 1
            if len(examples[t["style"]]) < 3:
                examples[t["style"]].append(f"{t['task_id']} (hidden: {', '.join(hit)})")
    with open(DS / "errata.jsonl", "w") as f:
        for e in errata:
            f.write(json.dumps(e) + "\n")
    checked = sum(len(v) for v in res.values() if "error" not in v)
    identical = sum(i["pixel_identical"] for v in res.values() if "error" not in v for i in v.values())
    failed = [k for k, v in res.items() if "error" in v]
    v10b = [e for e in errata if e["check"] == "V10b"]
    scenes_hit = len({e["task_id"].split("__")[0] for e in v10b})
    L = ["# Dataset audit", "",
         f"**{len(errata)} of {len(tasks)} tasks ({100 * len(errata) / len(tasks):.1f}%) are excluded** from every score, "
         "the evaluator, the demo and the human test (`dataset/errata.jsonl`). Both problems were found by drawing "
         "model answers on the images they saw (`overlays.py`), and both are fixed for new builds (checks version 2) "
         "while dataset v1.0 still rebuilds byte for byte.", "",
         "## Check V10b: labels hidden under the scale bar, north arrow or legend", "",
         "Dataset v1.0 was built before check V10b existed. `audit_labels.py` rebuilt every scene from its seed, "
         "re-rendered each image style exactly as built, and looked for option labels drawn under an area painted "
         "over the map afterwards: the 1 km scale bar, the north arrow, and (thermal) the colour legend. A hidden "
         "label can make a question unanswerable, so every such task is listed in `dataset/errata.jsonl` and left "
         "out of every score, the evaluator, the demo and the human test. New builds run V10b during generation: "
         "labels are placed clear of those areas, and a question whose labels are still hidden is dropped.", "",
         f"- Scene folders checked: **{len(res)}** ({len(failed)} could not be rebuilt)",
         f"- Images re-rendered: **{checked}**, pixel-identical to the published image: **{identical}**",
         f"- Tasks with a hidden option label: **{len(v10b)}** of {len(tasks)} "
         f"({100 * len(v10b) / len(tasks):.1f}%), in {scenes_hit} scenes; "
         f"the correct answer itself hidden in {sum(e['answer_hidden'] for e in v10b)}", "",
         "| Style | Tasks excluded | Examples |", "|---|---|---|"]
    for st in ("satellite", "map", "thermal"):
        L.append(f"| {st} | {per_style.get(st, 0)} | {'; '.join(examples.get(st, [])) or '–'} |")
    if failed:
        L += ["", "Could not be rebuilt (their tasks are kept, unaudited): " + ", ".join(failed[:20])]
    L += ["", "Found when the overlay of a model's answer showed village V1 of `level3_seed58561_cf` under the scale bar.",
          "", "## Count check: scenes with more items than their design allows", "",
          "In dataset v1.0, asking the placement routine for zero more items returned every free site instead of none. "
          "Most such scenes failed validation and were regenerated, but "
          f"**{len(over)} scenes** slipped through ({len(count_out)} tasks, base and twin): "
          + "; ".join(f"`{k}` ({v})" for k, v in sorted(over.items())) + ". Their answers were still verified "
          "independently, but a level-1 map with 55 villages is not the scene the difficulty dial describes, so "
          "every task of those scenes is excluded. New builds return no items for a zero request "
          "(`tests/test_tools.py::test_zero_count_pick_returns_nothing_in_checks_v2`).", ""]
    Path("docs").mkdir(exist_ok=True)
    Path("docs/AUDIT.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:3]))


if __name__ == "__main__":
    main()
