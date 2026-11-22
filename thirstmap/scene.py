"""Scene script: terrain + hydrology + where everything is placed.

A scene is pure data. Renderers turn it into images; questions.py turns it
into questions and answers. Same scene -> same answers in every image style.
"""
import math

import numpy as np

from .terrain import (CELL_M, N, accumulate, d8_receivers, dist, fractal, priority_flood,
                      rc, trace)


def build(seed, P, real=None):
    """Terrain, hydrology, and a data-centre site with an outfall. None if unusable.

    real: optional dict(z=elevation grid, landcover=class grid, name, credit) for real-terrain mode.
    """
    rng = np.random.default_rng(seed)
    rows, cols = np.mgrid[0:N, 0:N]
    if real is None:
        z = 40 + 75 * (1 - rows / N) + P["relief_m"] * fractal(rng, P["beta"])
        outlet = "south"
    else:
        z = real["z"].astype(float)
        outlet = "all"
    filled = priority_flood(z, outlet)
    lake = (filled - z) > 2.5
    disp = np.where(lake, filled, z)          # displayed elevation (lakes are flat)
    rec = d8_receivers(filled, outlet)
    acc = accumulate(filled, rec)
    stream = (acc >= P["stream_cells"]) & ~lake
    main = acc >= P["main_cells"]

    sites = [(r, c) for r in range(int(.15 * N), int(.55 * N), 2)
             for c in range(int(.15 * N), int(.85 * N), 2)]
    rng.shuffle(sites)
    for r, c in sites:
        if stream[r - 6:r + 7, c - 6:c + 7].any() or lake[r - 6:r + 7, c - 6:c + 7].any():
            continue
        d = np.hypot(rows - r, cols - c)
        cand = np.nonzero((stream & ~main & (d >= 8) & (d <= 14)
                           & (filled < filled[r, c] - 1)).ravel())[0]
        if len(cand) == 0:
            continue
        O = int(min(cand, key=lambda i: dist(i, r * N + c)))
        path = trace(rec, O)
        j = next((k for k, i in enumerate(path) if main.flat[i]), None)
        if j is None or j < 14 or len(path) < 45:
            continue
        return dict(outlet=outlet, real=real, drain_note=("Streams drain off the southern edge."
                    if outlet == "south" else "Water can leave the area across any edge."),
                    seed=seed, rng=rng, z=z, disp=disp, filled=filled, lake=lake, rec=rec,
                    acc=acc, stream=stream, main=main, site=r * N + c, O=O, path=path, junction=j)
    return None


def _pick_spaced(rng, pool, k, taken, min_d=10):
    pool = list(pool)
    rng.shuffle(pool)
    out = []
    for i in pool:
        if all(dist(i, t) >= min_d for t in taken + out):
            out.append(int(i))
            if len(out) == k:
                break
    return out


def _bank_cell(s, i):
    """A dry cell 2-3 cells from stream cell i, where the village houses sit."""
    r, c = rc(i)
    for rad in (2, 3, 4):
        for dr, dc in ((0, rad), (0, -rad), (rad, 0), (-rad, 0), (rad, rad), (-rad, -rad)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < N and 0 <= cc < N and not s["stream"][rr, cc] and not s["lake"][rr, cc]:
                return rr * N + cc
    return int(i)


def populate(s, P):
    """Place villages (with water intakes), wetland candidates, pond and farms."""
    rng, rec, path, O = s["rng"], s["rec"], s["path"], s["O"]
    on_path = set(path)
    stream_idx = np.nonzero(s["stream"].ravel())[0]
    near_path = lambda i: min(dist(i, p) for p in path[::2]) < 5
    upstream = [int(i) for i in stream_idx if i != O and O in set(trace(rec, i)) and dist(i, O) >= 6]
    off_path = [int(i) for i in stream_idx
                if i not in on_path and not near_path(i) and int(i) not in upstream]
    near_dc = [i for i in off_path if dist(i, s["site"]) < 32]
    taken = [s["site"], O]

    nv = P["n_villages"]
    down = _pick_spaced(rng, path[14:], max(2, nv // 2 - 1), taken, 12)
    trap_up = _pick_spaced(rng, upstream, 1, taken + down, 10)          # same stream, but upstream
    trap_near = _pick_spaced(rng, near_dc, 1, taken + down + trap_up, 10)  # close, other stream
    traps = trap_up + trap_near
    rest = _pick_spaced(rng, off_path, nv - len(down) - len(traps), taken + down + traps, 12)
    villages = down + traps + rest
    rng.shuffle(villages)

    first = min(path.index(v) for v in down) if down else len(path)
    taken2 = taken + villages
    good = _pick_spaced(rng, path[3:first - 3], 1, taken2, 6)
    late = _pick_spaced(rng, path[first + 3:], 1, taken2 + good, 6)    # after a village: too late
    wet_up = _pick_spaced(rng, upstream, 1, taken2 + good + late, 6)
    wrong = list(wet_up)
    wrong += _pick_spaced(rng, near_dc + off_path, 4 - len(good + late + wrong),
                          taken2 + good + late + wrong, 8)
    wet = good + late + wrong
    rng.shuffle(wet)

    sr, sc = rc(s["site"])
    pond = (sr + 5) * N + sc + 3
    pe = s["disp"].flat[pond]
    land = np.nonzero((~s["stream"] & ~s["lake"]).ravel())[0]

    def clear(i):
        r, c = rc(i)
        return not s["stream"][max(0, r - 2):r + 3, max(0, c - 3):c + 4].any()

    ring = [int(i) for i in land
            if 10 <= dist(i, pond) <= 34 and abs(s["disp"].flat[i] - pe) >= 3 and clear(i)]
    farms = _pick_spaced(rng, ring, P["n_farms"], taken2 + wet + [pond], 7)
    return dict(trap_up=trap_up, trap_near=trap_near, wet_late=late, wet_up=wet_up,
                villages=villages, village_pos={v: _bank_cell(s, v) for v in villages},
                wet=wet, good=good[0] if good else None, pond=pond, farms=farms)


def _outfall_for(s, site, dmin=6, dmax=12):
    """Nearest stream cell lower than the site: where its wastewater would enter."""
    r, c = rc(site)
    rows, cols = np.mgrid[0:N, 0:N]
    d = np.hypot(rows - r, cols - c)
    cand = np.nonzero((s["stream"] & (d >= dmin) & (d <= dmax)
                       & (s["filled"] < s["filled"][r, c] - 1)).ravel())[0]
    if len(cand) == 0:
        return None
    return int(min(cand, key=lambda i: dist(i, site)))


def add_siting(s, p, rng, bi):
    """Q6: three candidate sites S1-S3; exactly one sends its wastewater past no village."""
    stream, lake = s["stream"], s["lake"]
    taken = [s["site"], s["O"], p["pond"]] + p["villages"] + list(p["village_pos"].values()) + p["wet"] + p["farms"]
    clean, dirty = [], []
    cells = [(r, c) for r in range(14, N - 22, 3) for c in range(14, N - 14, 3)]
    rng.shuffle(cells)
    for r, c in cells:
        site = r * N + c
        if stream[r - 4:r + 5, c - 5:c + 6].any() or lake[r - 4:r + 5, c - 5:c + 6].any():
            continue
        if any(dist(site, t) < 12 for t in taken):
            continue
        o = _outfall_for(s, site)
        if o is None:
            continue
        path = trace(s["rec"], o)
        pset = set(path)
        hits = [v for v in p["villages"] if v in pset]
        if hits:
            dirty.append((site, o, path))
        elif min(dist(v, q) for v in p["villages"] for q in path[::2]) >= 6:
            clean.append((site, o, path))
        if len(clean) >= 3 and len(dirty) >= 6:
            break
    for good in clean:
        chosen = [good]
        for cand in dirty:
            if all(dist(cand[0], x[0]) >= 16 and dist(cand[1], x[1]) >= 6 for x in chosen):
                chosen.append(cand)
            if len(chosen) == 3:
                slot = bi % 3                          # balanced position of the correct answer (V14)
                sites = chosen[1:]
                sites.insert(slot, good)
                return dict(sites=[x[0] for x in sites], site_outfalls=[x[1] for x in sites],
                            site_paths=[x[2] for x in sites], clean_site=good[0])
    return None


def add_intake(s, p, P, rng, bi):
    """Q7: DC-1's water intake I; which villages are upstream of it (share its water)."""
    pset = set(s["path"])
    markers = [s["site"], s["O"], p["pond"]] + p["wet"] + p["farms"] + list(p["village_pos"].values())
    traces = {v: set(trace(s["rec"], v)) for v in p["villages"]}
    idx = [int(i) for i in np.nonzero((s["stream"] & (s["acc"] >= 2 * P["stream_cells"])).ravel())[0]]
    rng.shuffle(idx)
    target = 1 + (bi // 3) % 3                          # balanced answer-set size (V14)
    fallback = None
    for i in idx:
        if i in pset or any(dist(i, m) < 7 for m in markers):
            continue
        if any(dist(i, v) < 5 for v in p["villages"]):
            continue
        up = [v for v in p["villages"] if i in traces[v]]
        if 1 <= len(up) <= 3 and len(p["villages"]) - len(up) >= 2:
            if len(up) == target:
                return dict(intake=i, upstream=up)
            fallback = fallback or dict(intake=i, upstream=up)
    return fallback


def plume_values(path, acc, lake, dT0, lam):
    """Excess water temperature (deg C) at each cell of the path.

    Exponential cooling with distance (length scale lam, metres), extra
    dilution where a tributary joins, and mixing on entering a lake.
    """
    dT, out, in_lake = dT0, {}, False
    for k, i in enumerate(path):
        if k:
            prev = path[k - 1]
            step = CELL_M * (1.414 if abs(prev - i) not in (1, N) else 1.0)
            dT *= math.exp(-step / lam)
            if acc[i] > 1.3 * acc[prev]:
                dT *= (acc[prev] / acc[i]) ** 0.35
            if lake[i] and not in_lake:
                dT *= 0.6
            in_lake = bool(lake[i])
        out[i] = dT
    return out


def add_plume(s, rng, tries=300):
    """Q8/Q9: warm cooling water along the wastewater path."""
    for _ in range(tries):
        dT0, lam = rng.uniform(6, 15), rng.uniform(500, 4000)
        yield dict(dT0=dT0, lam_m=lam,
                   dT=plume_values(s["path"], s["acc"].ravel(), s["lake"].ravel(), dT0, lam))


def make(seed, P, max_tries=50, bi=None, real=None):
    """Build a valid scene, moving to a new seed if placement fails.

    bi (balance index) rotates answer positions/sizes so that, across a dataset,
    no answer is favoured (V14). Defaults to the seed.
    """
    bi = seed if bi is None else bi
    for k in range(max_tries):
        sd = seed + 1000 * k
        s = build(sd, P, real)
        if s:
            p = populate(s, P)
            if p["good"] is not None and len(p["farms"]) >= 2:
                rng = np.random.default_rng(sd + 5)
                p["siting"] = add_siting(s, p, rng, bi)
                p["intake"] = add_intake(s, p, P, rng, bi)
                p["plume"] = _choose_plume(s, p, rng, bi)
                return s, p
    raise RuntimeError("no valid scene found")


def _choose_plume(s, p, rng, bi, threshold=3.0, margin=0.8):
    """Warm-water plume + 4 monitoring points M1-M4 for the thermal questions.

    Points: 1-2 warm (> 3.8 C) on the wastewater path, 1 cooled-down point further
    downstream (< 2.2 C) when one exists, the rest on other streams (0 C),
    preferring the same stream just upstream of O (a trap). No point sits within
    0.8 C of the 3 C threshold.
    """
    path, lake = s["path"], s["lake"].ravel()
    markers = [s["site"], s["O"], p["pond"]] + p["wet"] + list(p["village_pos"].values())
    stream_idx = [int(i) for i in np.nonzero(s["stream"].ravel())[0]]
    pset = set(path)
    off = [i for i in stream_idx if i not in pset and min(dist(i, q) for q in path[::3]) >= 6]
    up = [i for i in stream_idx if i not in pset and s["O"] in set(trace(s["rec"], i)) and dist(i, s["O"]) >= 6]
    inner = lambda i: 10 <= rc(i)[0] < N - 10 and 10 <= rc(i)[1] < N - 10
    off, up = [i for i in off if inner(i)], [i for i in up if inner(i)]
    n_warm = 1 + bi % 2
    for plume in add_plume(s, rng):
        dT = plume["dT"]
        warm = [i for i in path[4:] if 3.8 <= dT[i] <= 14.5 and not lake[i] and inner(i)]
        cool = [i for i in path if 0.4 <= dT[i] <= 2.2 and not lake[i] and inner(i)]
        if len(warm) < n_warm:
            continue
        pts = _pick_spaced(rng, warm, n_warm, markers, 8)
        if len(pts) < n_warm:
            continue
        kind = {i: "warm" for i in pts}
        for k_name, pool, n in (("cooled_downstream", cool, 1), ("upstream_of_O", up, 1)):
            got = _pick_spaced(rng, pool, n, markers + pts, 8)
            kind.update({i: k_name for i in got}); pts += got
        got = _pick_spaced(rng, off, 4 - len(pts), markers + pts, 10)
        kind.update({i: "other_stream" for i in got}); pts += got
        if len(pts) < 4:
            continue
        rng.shuffle(pts)
        plume["point_kind"] = kind
        plume["points"] = pts
        plume["point_dT"] = {i: dT.get(i, 0.0) for i in pts}
        return plume
    return None
