"""Rebuild any dataset scene (or its counterfactual twin) in memory from its recorded seed.

Used by analyses that need positions the task files do not store (villages, wetlands, sites, the true
water path). Every rebuild is checked against the stored answer key; a mismatch raises, so an analysis can
never silently use the wrong scene.
"""
import json
from pathlib import Path

from .counterfactual import make_twin
from .questions import answer_key
from .scene import make
from .terrain import params

BASE_SEED = 1000


def _balance_candidates(key):
    """Balance indexes that could have produced this scene (newer keys record it directly)."""
    if "balance_index" in key:
        return [key["balance_index"]]
    level, seed, out = key["level"], key["seed"], []
    for k in range(500):
        base = BASE_SEED + 97 * k + 10007 * level
        for t in range(20):
            rest = seed - base - 7919 * t
            if rest >= 0 and rest % 1000 == 0 and rest // 1000 < 60:
                out.append(k)
    return out


def _matches(qs, stored):
    got = {q["id"]: q["answer"] for q in qs}
    return all(got.get(q["id"]) == q["answer"] for q in stored)


def rebuild(dataset, scene_id):
    """Return dict(s, p, nm, P, key) for a scene folder name, base or `_cf` twin."""
    ds = Path(dataset)
    key = json.loads((ds / "scenes" / scene_id / "answer_key.json").read_text())
    base_id = key.get("pair_of") or scene_id
    bkey = key if base_id == scene_id else json.loads((ds / "scenes" / base_id / "answer_key.json").read_text())
    P = dict(bkey["params"]) if "params" in bkey else params(bkey["level"])     # carries the checks version
    R = None
    if bkey.get("terrain", "synthetic") != "synthetic":
        from . import realterrain
        R = realterrain.load(bkey["terrain"])
    for k in _balance_candidates(bkey):
        s, p = make(bkey["seed"], P, bi=k, real=R)
        qs, nm, _ = answer_key(s, p)
        if _matches(qs, bkey["questions"]):
            break
    else:
        raise RuntimeError(f"{base_id}: no seed candidate reproduces the stored answers")
    if base_id == scene_id:
        return dict(s=s, p=p, nm=nm, P=P, key=key)
    made = make_twin(s, p, P, key["cf_kind"], bkey["questions"])
    if not made:
        raise RuntimeError(f"{scene_id}: twin could not be rebuilt")
    s2, p2, _, _ = made
    qs2, nm2, _ = answer_key(s2, p2)
    if not _matches(qs2, key["questions"]):
        raise RuntimeError(f"{scene_id}: rebuilt twin does not reproduce the stored answers")
    return dict(s=s2, p=p2, nm=nm2, P=P, key=key)


def label_cells(r):
    """Map every answer label in a rebuilt scene to the grid cell where it is drawn."""
    s, p, nm = r["s"], r["p"], r["nm"]
    out = {}
    for v in p["villages"]:
        out[nm["village"][v]] = p["village_pos"][v]
    for kind in ("wetland", "farm", "site", "monitor"):
        for cell, name in nm.get(kind, {}).items():
            out[name] = cell
    return out
