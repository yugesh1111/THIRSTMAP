"""Counterfactual twins: one minimal, visible change to a scene that MUST flip an answer.

Everything else (terrain, villages, labels, other markers) stays identical, so a model
that truly reads the image changes its answer, while one that answers from habit or
priors gives the same answer twice and fails one of the pair.

Kinds (rotated across the dataset):
  outfall : the wastewater pipe is rerouted to a different stream (O moves)  -> Q1, Q2 flip
  intake  : the water intake I moves to a nearby point of the network       -> Q7 flips
  thermal : the cooling-water temperature changes (colours only)            -> Q8, Q9 flip
"""
import numpy as np

from .scene import plume_values
from .terrain import N, dist, rc, trace

KINDS = ("outfall", "intake", "thermal")


def _hits(path, villages):
    pos = {i: k for k, i in enumerate(path)}
    return sorted([v for v in villages if v in pos], key=pos.get)


def move_outfall(s, p, P):
    site = s["site"]
    sr, sc = rc(site)
    rows, cols = np.mgrid[0:N, 0:N]
    d = np.hypot(rows - sr, cols - sc)
    cand = np.nonzero((s["stream"] & ~s["main"] & (d >= 8) & (d <= 30)
                       & (s["filled"] < s["filled"].flat[site] - 1)).ravel())[0]
    base_hits = set(_hits(s["path"], p["villages"]))
    base_path = set(s["path"])
    markers = [p["pond"]] + p["wet"] + p["farms"] + list(p["village_pos"].values())
    for o in sorted((int(i) for i in cand), key=lambda i: dist(i, site)):
        if o in base_path or any(dist(o, m) < 5 for m in markers):
            continue
        path = trace(s["rec"], o)
        hits = _hits(path, p["villages"])
        if not hits or set(hits) == base_hits or len(path) < 25:
            continue
        pset = set(path)
        others = [v for v in p["villages"] if v not in pset]
        if others and min(dist(v, q) for v in others for q in path) < 5:
            continue                      # an unaffected village too close to the new path: ambiguous
        return (dict(s, O=o, path=path), dict(p, good=None, plume=None), ["Q1", "Q2"],
                "the wastewater pipe is rerouted: outfall O moves to a different stream")
    return None


def move_intake(s, p, P):
    itk = p.get("intake")
    if not itk:
        return None
    markers = [s["site"], s["O"], p["pond"]] + p["wet"] + p["farms"] + list(p["village_pos"].values())
    traces = {v: set(trace(s["rec"], v)) for v in p["villages"]}
    pset = set(s["path"])
    idx = [int(i) for i in np.nonzero((s["stream"] & (s["acc"] >= 2 * P["stream_cells"])).ravel())[0]]
    for i in sorted(idx, key=lambda i: dist(i, itk["intake"])):   # nearest first: smallest visible move
        if i == itk["intake"] or i in pset:
            continue
        if any(dist(i, m) < 7 for m in markers) or any(dist(i, v) < 5 for v in p["villages"]):
            continue
        up = [v for v in p["villages"] if i in traces[v]]
        if 1 <= len(up) <= 3 and len(p["villages"]) - len(up) >= 2 and set(up) != set(itk["upstream"]):
            return (s, dict(p, intake=dict(intake=i, upstream=up), plume=None), ["Q7"],
                    "intake I moves to a different point of the stream network")
    return None


def change_plume(s, p, P, base_probe=None):
    pl = p.get("plume")
    if not pl:
        return None
    base_warm = {i for i, t in pl["point_dT"].items() if t > 3.0}
    for f in (0.45, 1.8, 0.6, 2.2, 0.35, 1.5, 0.3, 2.6, 0.5, 1.3, 0.25, 3.0, 0.7, 2.0):
        dT0 = pl["dT0"] * f
        if dT0 > 15.0:
            continue
        dT = plume_values(s["path"], s["acc"].ravel(), s["lake"].ravel(), dT0, pl["lam_m"])
        pdT = {i: dT.get(i, 0.0) for i in pl["points"]}
        if {i for i, t in pdT.items() if t > 3.0} == base_warm:
            continue                      # Q8 must flip
        if any(abs(t - 3.0) < 0.8 for t in pdT.values()):
            continue                      # keep the threshold margin
        qids = ["Q8"]
        if base_probe is not None and abs(pdT[base_probe] - pl["point_dT"][base_probe]) >= 3.0:
            qids.append("Q9")             # Q9 pairs only when the value moves by > 2x its tolerance
        return (s, dict(p, plume=dict(pl, dT0=dT0, dT=dT, point_dT=pdT), q9_probe=base_probe),
                qids, f"the cooling water is {'cooler' if f < 1 else 'hotter'} (x{f} at the outfall)")
    return None


def make_twin(s, p, P, kind, base_questions):
    probe = next((q.get("point") for q in base_questions if q["id"] == "Q9"), None)
    if kind == "outfall":
        return move_outfall(s, p, P)
    if kind == "intake":
        return move_intake(s, p, P)
    return change_plume(s, p, P, probe)
