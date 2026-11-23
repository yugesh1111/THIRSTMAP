"""Generate one ThirstMap scene: every image style, answer key, validation report, reveals.

Usage: python3 generate.py --level 3 --seed 11 [--out out]
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from thirstmap import render_map, render_sat, render_thermal
from thirstmap.questions import answer_key
from thirstmap.render_sat import _px
from thirstmap import realterrain
from thirstmap.counterfactual import KINDS, make_twin
from thirstmap.scene import make
from thirstmap.terrain import L_KM, params
from thirstmap.validate import validate


def render_all(s, p, nm, P, truth, tag, strict=False):
    """Render every style. Returns {style: (image, reveal_image)} and validator inputs."""
    out, images = {}, {}
    sat = render_sat.render(s, p, nm, P, title=f"{tag} | satellite-style | {s['drain_note'].lower()}", reserve=strict)
    out["satellite"] = (sat, render_sat.render(
        s, p, nm, P, reveal=True, truth=truth,
        title="ANSWER KEY | red = wastewater path, red rings = affected villages | green = working wetland / "
              "clean site | blue rings = upstream of intake I", reserve=strict))
    off = sat.info["offset"]
    images["satellite"] = (np.asarray(sat), lambda i: (_px(i)[0], _px(i)[1] + off), sat.info["labels"],
                           sat.info["reserved"])
    if p.get("plume"):
        th = render_thermal.render(s, p, nm, P, title=f"{tag} | thermal: water temperature above normal", reserve=strict)
        out["thermal"] = (th, render_thermal.render(
            s, p, nm, P, reveal=True, truth=truth, title="ANSWER KEY | red rings = water > 3 °C warmer than normal",
            reserve=strict))
        images["thermal"] = (np.asarray(th), lambda i: (_px(i)[0], _px(i)[1] + off), th.info["labels"],
                             th.info["reserved"])
    fig = render_map.render(s, p, nm, P, title=f"{tag} | topographic map")
    arr = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    images["map"] = (arr, fig.tm_px, fig.tm_labels, fig.tm_reserved)
    fig_r = render_map.render(s, p, nm, P, reveal=True, truth=truth,
                              title="ANSWER KEY | red = wastewater path | ✓ = gravity-fed farm | "
                                    "green = working wetland / clean site | blue = upstream of I")
    out["map"] = (fig, fig_r)
    return out, images


def save(img, path):
    if hasattr(img, "savefig"):
        img.savefig(path)
        plt.close(img)
    else:
        img.save(path)


def generate(level, seed, out_root, max_tries=20, bi=None, real=None, twin=False, strict=True):
    """strict=True: dataset checks version 2 (V10b on, labels kept clear of the scale bar, north arrow and legend).
    strict=False rebuilds dataset v1.0 scenes byte for byte."""
    P = dict(params(level), checks=2) if strict else params(level)
    R = realterrain.load(real) if real else None
    for k in range(max_tries):
        s, p = make(seed + 7919 * k, P, bi=bi, real=R)
        qs, nm, truth = answer_key(s, p)
        tag = (f"Region TM-{s['seed']:05d} | difficulty {level}/5 | {L_KM:.0f} km x {L_KM:.0f} km" if not R else
               f"{R['desc']} | hypothetical facility | {L_KM:.0f} km x {L_KM:.0f} km")
        rendered, images = render_all(s, p, nm, P, truth, tag, strict)
        report = validate(s, p, qs, nm, images, strict=strict)
        if report["scene_ok"]:
            break
        for a, b in rendered.values():
            for im in (a, b):
                if hasattr(im, "savefig"):
                    plt.close(im)
    else:
        raise RuntimeError("no scene passed validation")

    out = Path(out_root) / (f"real_{real}_seed{s['seed']}" if real else f"level{level}_seed{s['seed']}")
    out.mkdir(parents=True, exist_ok=True)
    for style, (img, rev) in rendered.items():
        save(img, out / f"{style}.png")
        save(rev, out / f"{style}_reveal.png")
    kept = [dict(q, styles=report["styles"][q["id"]]) for q in qs if q["id"] in report["keep"]]
    (out / "answer_key.json").write_text(json.dumps(
        {"scene_id": out.name, "seed": s["seed"], "level": level, "params": P, "questions": kept,
         "terrain": real or "synthetic", "drain_note": s["drain_note"],
         "credit": R["credit"] if R else None, "balance_index": bi, **({"checks": 2} if strict else {})},
        indent=2, ensure_ascii=False))
    (out / "validation.json").write_text(json.dumps(report, indent=2, default=str))
    if not twin:
        return out, kept, report
    return out, kept, report, build_twin(s, p, P, kept, out, tag, level, real, R, bi if bi is not None else seed, strict)


def build_twin(s, p, P, base_kept, base_out, tag, level, real, R, bi, strict=True):
    """Counterfactual twin: same scene, one minimal change, answers must flip. None if impossible."""
    base = {q["id"]: q for q in base_kept}
    for kind in KINDS[bi % 3:] + KINDS[:bi % 3]:              # rotate kinds across the dataset
        made = make_twin(s, p, P, kind, base_kept)
        if not made:
            continue
        s2, p2, qids, change = made
        qs2, nm2, truth2 = answer_key(s2, p2)
        rendered, images = render_all(s2, p2, nm2, P, truth2, tag + " | counterfactual twin", strict)
        report = validate(s2, p2, qs2, nm2, images, strict=strict)
        pairs = []
        for q in qs2:
            b = base.get(q["id"])
            if q["id"] in qids and q["id"] in report["keep"] and b and q["answer"] != b["answer"]:
                styles = [st for st in report["styles"][q["id"]] if st in b["styles"]]
                if styles:
                    pairs.append(dict(q, styles=styles))
        if not report["scene_ok"] or not pairs:
            for a, b in rendered.values():
                for im in (a, b):
                    if hasattr(im, "savefig"):
                        plt.close(im)
            continue
        out = base_out.parent / (base_out.name + "_cf")
        out.mkdir(parents=True, exist_ok=True)
        used = {st for q in pairs for st in q["styles"]}
        for style, (img, rev) in rendered.items():
            if style in used:
                save(img, out / f"{style}.png")
                save(rev, out / f"{style}_reveal.png")
            elif hasattr(img, "savefig"):
                plt.close(img); plt.close(rev)
        (out / "answer_key.json").write_text(json.dumps(
            {"scene_id": out.name, "pair_of": base_out.name, "cf_kind": kind, "cf_change": change,
             "seed": s["seed"], "level": level, "params": P, "questions": pairs,
             "terrain": real or "synthetic", "drain_note": s["drain_note"],
             "credit": R["credit"] if R else None, **({"checks": 2} if strict else {})}, indent=2, ensure_ascii=False))
        (out / "validation.json").write_text(json.dumps(report, indent=2, default=str))
        return dict(folder=out, kept=pairs, kind=kind, change=change)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=3)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default="out")
    ap.add_argument("--real", choices=sorted(realterrain.LOCATIONS), help="use real terrain for this location")
    ap.add_argument("--twin", action="store_true", help="also build the counterfactual twin")
    a = ap.parse_args()
    res = generate(a.level, a.seed, a.out, real=a.real, twin=a.twin)
    out, kept, report = res[:3]
    if a.twin:
        tw = res[3]
        print("twin:", f"{tw['folder']} ({tw['kind']}: {tw['change']}) questions {[q['id'] for q in tw['kept']]}"
              if tw else "none possible for this scene")
    print(out)
    for name, c in report["checks"].items():
        print(f"  {'PASS' if c['passed'] else 'FAIL'}  {name}  "
              f"{ {k: v for k, v in c.items() if k != 'passed'} }")
    print("  kept:", report["keep"], " dropped:", report["drop"])


if __name__ == "__main__":
    main()
