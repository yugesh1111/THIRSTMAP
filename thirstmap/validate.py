"""Validators. A question is kept only if every check relevant to it passes.

V1  independent answer recomputation with a third-party hydrology library (pysheds)
V5  elevation margin (gravity question)
V7  spatial margin: unaffected villages are clearly away from the wastewater path
V8  exactly one correct wetland
V9  the evidence is visible in the rendered pixels (each image style)
V10 labels are inside the image and do not overlap
V11 questions are only asked in styles that contain the evidence
Q8  temperature margin around the 3 deg C threshold
Nothing is ever hand-edited: failing questions are dropped, failing scenes are regenerated.
"""
import numpy as np

from .questions import flow_direction
from .render_thermal import colour
from .scene import plume_values
from .terrain import N, dist, outlet_mask, polyline_length_m, trace

DIRS = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
EVIDENCE_STYLES = {"Q1": {"map", "satellite"}, "Q2": {"map", "satellite"}, "Q3": {"map", "satellite"},
                   "Q4": {"map"}, "Q5": {"map", "satellite"}, "Q6": {"map", "satellite"},
                   "Q7": {"map", "satellite"}, "Q8": {"thermal"}, "Q9": {"thermal"},
                   "Q10": {"map", "satellite"}}


def pysheds_routing(filled, outlet="south"):
    """Flow receivers + accumulation computed by pysheds (independent implementation)."""
    from affine import Affine
    from pysheds.grid import Grid
    from pysheds.sview import Raster, ViewFinder
    vf = ViewFinder(affine=Affine(1, 0, 0, 0, -1, N), shape=(N, N), nodata=-9999.0)
    dem = Raster(filled.astype(np.float64), viewfinder=vf)
    grid = Grid.from_raster(dem)
    dirmap = tuple(DIRS)
    fd = np.asarray(grid.flowdir(dem, dirmap=dirmap))
    rec = -np.ones(N * N, int)
    for code, (dr, dc) in DIRS.items():
        rr, cc = np.nonzero(fd == code)
        ok = (rr + dr >= 0) & (rr + dr < N) & (cc + dc >= 0) & (cc + dc < N)
        rec[rr[ok] * N + cc[ok]] = (rr[ok] + dr) * N + (cc[ok] + dc)
    rec[outlet_mask(outlet).ravel()] = -1      # same boundary condition as the generator
    return rec, topo_accumulation(rec)


def topo_accumulation(rec):
    """Flow accumulation by topological ordering (Kahn's algorithm).

    Deliberately a different algorithm from the generator's (which sorts by
    elevation), so the two can disagree if either is wrong. pysheds' own
    accumulation is not used because it fails on NumPy 2.
    """
    indeg = np.zeros(N * N, int)
    for r in rec:
        if r >= 0:
            indeg[r] += 1
    acc = np.ones(N * N)
    stack = [i for i in range(N * N) if indeg[i] == 0]
    while stack:
        i = stack.pop()
        r = rec[i]
        if r >= 0:
            acc[r] += acc[i]
            indeg[r] -= 1
            if indeg[r] == 0:
                stack.append(r)
    return acc


def independent_answers(s, p, nm, qs=None):
    rec2, acc2 = pysheds_routing(s["filled"], s.get("outlet", "south"))
    path2 = trace(rec2, s["O"])
    pos2 = {i: k for k, i in enumerate(path2)}
    hit2 = sorted([v for v in p["villages"] if v in pos2], key=pos2.get)
    ans = {"Q1": sorted(nm["village"][v] for v in hit2),
           "Q2": nm["village"][hit2[0]] if hit2 else "none"}
    if hit2:
        d_m = polyline_length_m(path2[: pos2[hit2[0]] + 1])
        if d_m >= 300:
            ans["Q10"] = int(round(d_m, -1))
    first = pos2[hit2[0]] if hit2 else len(path2)
    good = [w for w in p["wet"] if w in pos2 and pos2[w] < first]
    ans["Q3"] = nm["wetland"][good[0]] if len(good) == 1 else f"AMBIGUOUS({len(good)})"
    pe = s["disp"].flat[p["pond"]]
    ans["Q4"] = sorted(nm["farm"][f] for f in p["farms"] if s["disp"].flat[f] < pe)
    fd = flow_direction({"O": s["O"], "path": path2})
    if fd:
        ans["Q5"] = fd
    sit = p.get("siting")
    if sit:
        clean = [k for k, o in enumerate(sit["site_outfalls"])
                 if not set(trace(rec2, o)) & set(p["villages"])]
        ans["Q6"] = f"S{clean[0] + 1}" if len(clean) == 1 else f"AMBIGUOUS({len(clean)})"
    itk = p.get("intake")
    if itk:
        ans["Q7"] = sorted(nm["village"][v] for v in p["villages"] if itk["intake"] in set(trace(rec2, v)))
    pl = p.get("plume")
    if pl:
        vals = plume_values(path2, acc2.ravel(), s["lake"].ravel(), pl["dT0"], pl["lam_m"])
        ans["Q8"] = sorted(nm["monitor"][i] for i in pl["points"] if vals.get(i, 0.0) > 3.0)
        probe = next((q["point"] for q in (qs or []) if q["id"] == "Q9"), None)
        if probe is not None:
            ans["Q9"] = round(vals.get(probe, 0.0), 1)
    agree = float(np.mean(rec2 == s["rec"]))
    return ans, agree


def _same(q, a, b):
    if q == "Q9":
        return isinstance(b, float) and abs(a - b) <= 0.3
    if q == "Q10":
        return isinstance(b, (int, float)) and abs(a - b) <= 0.05 * a
    return a == b


# ---------------------------------------------------------------- pixel evidence
def _water_like(style, px, dT=None):
    r, g, b = px[..., 0].astype(int), px[..., 1].astype(int), px[..., 2].astype(int)
    if style == "satellite":
        return bool(((b - r) >= 12).any())
    if style == "map":
        return bool(((b - r) >= 60).any())
    if style == "thermal":
        c = np.array(colour(dT))
        return bool((np.abs(px.astype(int) - c).sum(-1) <= 60).any())
    raise ValueError(style)


def path_visibility(style, arr, to_px, cells, dT=None, win=5):
    """Fraction of answer-path cells whose pixels look like water in this style."""
    ok = 0
    for i in cells:
        x, y = to_px(i)
        x, y = int(round(x)), int(round(y))
        patch = arr[max(0, y - win):y + win + 1, max(0, x - win):x + win + 1, :3]
        ok += _water_like(style, patch, None if dT is None else dT.get(i, 0.0))
    return ok / max(1, len(cells))


def label_overlaps(labels, size):
    W, H = size
    bad = []
    for k, (ta, a) in enumerate(labels):
        if a[0] < 0 or a[1] < 0 or a[2] > W or a[3] > H:
            bad.append(f"{ta} outside image")
        for tb, b in labels[k + 1:]:
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                bad.append(f"{ta}/{tb}")
    return bad


# ---------------------------------------------------------------- main entry
def validate(s, p, qs, nm, images):
    """images: {style: (rgb ndarray, cell->pixel fn, label boxes)}. Returns report dict."""
    checks, drop = {}, {}
    key = {q["id"]: q for q in qs}

    # V1: independent recomputation
    ind, agree = independent_answers(s, p, nm, qs)
    mism = {q: (key[q]["answer"], ind.get(q)) for q in key if not _same(q, key[q]["answer"], ind.get(q))}
    checks["V1_independent_pysheds"] = dict(passed=not mism, receiver_agreement=round(agree, 4),
                                            mismatches={k: list(map(str, v)) for k, v in mism.items()})
    for q in mism:
        drop[q] = "V1 mismatch with independent implementation"

    # V5: gravity margin
    pe = s["disp"].flat[p["pond"]]
    gaps = [abs(s["disp"].flat[f] - pe) for f in p["farms"]]
    checks["V5_elevation_margin"] = dict(passed=min(gaps) >= 3.0, min_gap_m=round(min(gaps), 2))
    if min(gaps) < 3.0:
        drop["Q4"] = "V5 farm within 3 m of pond"

    # V7: unaffected villages are away from the path
    pset = set(s["path"])
    far = [min(dist(v, q) for q in s["path"]) for v in p["villages"] if v not in pset]
    ok7 = not far or min(far) >= 5
    checks["V7_spatial_margin"] = dict(passed=ok7, min_cells=round(min(far), 2) if far else None)
    if not ok7:
        drop["Q1"] = drop["Q2"] = "V7 unaffected village too close to path"

    # V8: exactly one wetland before the first village, others clearly off that stretch
    pos = {i: k for k, i in enumerate(s["path"])}
    hit = sorted([v for v in p["villages"] if v in pos], key=pos.get)
    first = pos[hit[0]] if hit else len(s["path"])
    stretch = s["path"][:first]
    good = [w for w in p["wet"] if w in pos and pos[w] < first]
    others = [min(dist(w, q) for q in stretch) for w in p["wet"] if w not in good]
    ok8 = len(good) == 1 and (not others or min(others) >= 3)
    checks["V8_single_wetland"] = dict(passed=ok8, n_correct=len(good))
    if not ok8:
        drop["Q3"] = "V8 wetland answer not unique"

    # Q8 temperature margin
    pl = p.get("plume")
    if pl:
        m = min(abs(t - 3.0) for t in pl["point_dT"].values())
        checks["V_temp_margin"] = dict(passed=m >= 0.8, min_margin_c=round(m, 2))
        if m < 0.8:
            drop["Q8"] = "temperature within 0.8 C of threshold"

    # V9: evidence visible in pixels, per style
    cells = s["path"][2: (pos[hit[-1]] + 1) if hit else 40]     # first cells sit under the O marker
    style_drop = {}
    for style, (arr, to_px, labels) in images.items():
        dT = pl["dT"] if (style == "thermal" and pl) else None
        frac = path_visibility(style, arr, to_px, cells, dT)
        checks[f"V9_path_visible_{style}"] = dict(passed=frac >= 0.9, fraction=round(frac, 3))
        if frac < 0.9:
            for q, st in EVIDENCE_STYLES.items():
                if style in st and q in key:
                    style_drop.setdefault(q, []).append(style)
        bad = label_overlaps(labels, (arr.shape[1], arr.shape[0]))
        checks[f"V10_labels_{style}"] = dict(passed=not bad, problems=bad[:6])

    # V11: questions only in styles with evidence
    wrong = [q["id"] for q in qs if not set(q["styles"]) <= EVIDENCE_STYLES[q["id"]]]
    checks["V11_style_applicability"] = dict(passed=not wrong, wrong=wrong)

    # a question survives in the styles that still hold the evidence
    styles = {}
    for q in qs:
        left = [st for st in q["styles"] if st not in style_drop.get(q["id"], [])]
        if not left:
            drop.setdefault(q["id"], "V9 evidence not visible in any style")
        styles[q["id"]] = left
    scene_ok = all(c["passed"] for k, c in checks.items() if k.startswith("V10")) and not wrong
    keep = [q["id"] for q in qs if q["id"] not in drop]
    return dict(scene_ok=scene_ok, checks=checks, keep=keep, drop=drop,
                styles={k: v for k, v in styles.items() if k in keep}, style_drop=style_drop)
