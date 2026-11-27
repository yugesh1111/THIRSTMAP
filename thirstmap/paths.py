"""Draw the water's path: the model traces where the wastewater goes, and the line it draws is scored against the
simulated path, cell by cell.

A right list of villages can come from a wrong route (a lucky guess, a label read off the wrong stream). Because the
simulation knows the whole route, ThirstMap can check the reasoning itself, not only the final answer.

Coordinates. The model answers in normalised image coordinates: x and y run from 0 to 1000 across the whole image it
was shown (top-left origin), so the score does not depend on how the image was resized. Named keys ("x", "y") remove
any doubt about axis order. Each answer is mapped back onto the terrain grid through the renderer's own affine
pixel mapping, recorded per image (`frame`).

Score. Both lines are densified to half-cell steps. precision = share of the drawn line within TOL cells of the true
path; recall = share of the true path within TOL cells of the drawn line; a trace passes when both reach PASS.
Path cells inside a lake are skipped for recall (the route across open water is not defined), and drawn points over
a lake the path crosses count as on the path. Points off the path are named: on a stream upstream of the outfall
(traced the wrong way), on another stream (jumped streams), on dry land (cut across), or outside the map.
"""
import json
import math
import re

import numpy as np

from .terrain import N, rc

TOL = 4                    # cells (100 m; 2.5% of the map's width)
PASS = 0.8                 # precision and recall both at least this
CURVE = (1, 2, 3, 4, 6, 8)

PROMPT = (
    "Cooling-tower wastewater from DC-1 enters the stream at outfall O. Trace the route this water takes downstream "
    "until it leaves the area shown, following the streams exactly as they appear in the image, and list the villages "
    "the water reaches.\n\n"
    "Reply with ONLY a JSON object of the form {\"path\": [{\"x\": 512, \"y\": 140}, ...], \"villages\": [\"V1\", ...]} "
    "where path lists 10 to 40 points in order along the route, starting at O (x runs from 0 at the left edge of the "
    "image to 1000 at the right edge, and y from 0 at the top edge to 1000 at the bottom edge), and villages lists "
    "every village the water reaches ([] if none)."
)


# ---------------------------------------------------------------------------------------------------------------------
# where things are in an image
# ---------------------------------------------------------------------------------------------------------------------
def frame_sat(width=800, height=830, bar=30, px_per_cell=5):
    """Satellite and thermal styles: cell (r, c) is drawn at ((c + .5) * 5, (r + .5) * 5 + bar)."""
    return dict(size=[width, height], x0=0.0, sx=float(px_per_cell), y0=float(bar), sy=float(px_per_cell))


def frame_map(fig):
    """Topographic map: fit the (linear) axes transform from two cells."""
    a, b = 0, N * N - 1
    (xa, ya), (xb, yb) = fig.tm_px(a), fig.tm_px(b)
    (ra, ca), (rb, cb) = rc(a), rc(b)
    sx, sy = (xb - xa) / (cb - ca), (yb - ya) / (rb - ra)
    w, h = fig.canvas.get_width_height()
    return dict(size=[w, h], x0=xa - sx * (ca + .5), sx=sx, y0=ya - sy * (ra + .5), sy=sy)


def cell_to_norm(i, F):
    r, c = rc(i)
    return ((F["x0"] + F["sx"] * (c + .5)) / F["size"][0] * 1000, (F["y0"] + F["sy"] * (r + .5)) / F["size"][1] * 1000)


def norm_to_grid(x, y, F):
    """Normalised image point -> continuous grid position (row, col), cell centres at integers."""
    px, py = x / 1000 * F["size"][0], y / 1000 * F["size"][1]
    return (py - F["y0"]) / F["sy"] - .5, (px - F["x0"]) / F["sx"] - .5


def truth_record(s, F, style, image):
    """Everything the scorer needs about one image, as plain JSON (no rebuild needed at scoring time)."""
    O, path, rec = s["O"], s["path"], s["rec"]
    stream = s["stream"].ravel() | s["lake"].ravel()
    # every cell whose water passes through O, i.e. upstream of the outfall
    order = np.argsort(-s["filled"], axis=None)
    flows_to_O = np.zeros(N * N, bool)
    flows_to_O[O] = True
    for i in order[::-1]:                    # low to high: a cell flows to O if its receiver does
        r_ = rec[i]
        if r_ >= 0 and flows_to_O[r_]:
            flows_to_O[i] = True
    up = [int(i) for i in np.nonzero(flows_to_O & stream)[0] if i != O]
    lakes_on_path = sorted({int(i) for i in np.nonzero(s["lake"].ravel())[0]} & set(map(int, path)))
    return dict(image=image, style=style, frame=F, O=int(O), path=[int(i) for i in path],
                stream=[int(i) for i in np.nonzero(stream)[0]], upstream=up,
                lake_cells=_lake_cells_touching(s, lakes_on_path))


def _lake_cells_touching(s, seeds):
    """All cells of the lakes the path crosses (flood fill from the path's lake cells)."""
    lake = s["lake"].ravel()
    out, todo = set(seeds), list(seeds)
    while todo:
        i = todo.pop()
        r, c = rc(i)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                j = rr * N + cc
                if 0 <= rr < N and 0 <= cc < N and lake[j] and j not in out:
                    out.add(j)
                    todo.append(j)
    return sorted(out)


# ---------------------------------------------------------------------------------------------------------------------
# reading a reply
# ---------------------------------------------------------------------------------------------------------------------
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_villages(raw):
    """The "villages" list of a reply (raw strings), or None."""
    txt = re.sub(r"```(?:json)?", "", raw or "")
    for m in reversed(list(re.finditer(r"\{.*\}", txt, re.S))):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            continue
        if isinstance(obj, dict) and "villages" in obj:
            return obj["villages"]
    m = re.search(r'"villages"\s*:\s*(\[[^\]]*\])', txt)
    if m:
        try:
            return json.loads(m.group(1))
        except ValueError:
            pass
    return None


def villages_on_line(points, T, tol=3):
    """Labels of the villages whose intake (the stream cell they draw from) lies within `tol` cells of the drawn line."""
    if not points:
        return []
    drawn = densify([norm_to_grid(x, y, T["frame"]) for x, y in points])
    out = []
    for name, cell in T["villages"].items():
        r, c = rc(cell)
        if np.hypot(drawn[:, 0] - r, drawn[:, 1] - c).min() <= tol:
            out.append(name)
    return sorted(out, key=lambda v: int(v[1:]))


def parse(raw):
    """Points [(x, y)] from a reply, in normalised 0-1000 coordinates; None if there is no usable path.

    Accepted: {"path": [{"x": .., "y": ..}, ...]} (asked for), or a list of [x, y] pairs in that order."""
    txt = re.sub(r"```(?:json)?", "", raw or "")
    obj = None
    for m in reversed(list(re.finditer(r"\{.*\}|\[.*\]", txt, re.S))):
        try:
            obj = json.loads(m.group(0))
            break
        except ValueError:
            continue
    if obj is None:                                   # cut-off JSON: keep every complete {"x": .., "y": ..}
        pts = [(float(a), float(b)) for a, b in re.findall(r'"x"\s*:\s*(-?[\d.]+)\s*,\s*"y"\s*:\s*(-?[\d.]+)', txt)]
        return pts if len(pts) >= 2 else None
    seq = obj.get("path") if isinstance(obj, dict) else obj
    if isinstance(seq, dict):
        seq = seq.get("points")
    if not isinstance(seq, list):
        return None
    pts = []
    for q in seq:
        if isinstance(q, dict):
            x, y = _num(q.get("x")), _num(q.get("y"))
        elif isinstance(q, (list, tuple)) and len(q) >= 2:
            x, y = _num(q[0]), _num(q[1])
        else:
            x = y = None
        if x is not None and y is not None:
            pts.append((x, y))
    return pts if len(pts) >= 2 else None


# ---------------------------------------------------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------------------------------------------------
def densify(pts, step=.5):
    pts = [tuple(map(float, q)) for q in pts]
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, math.ceil(math.dist(a, b) / step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    out.append(pts[-1])
    return np.array(out)


def _nearest(a, b):
    """For every point of a, the distance to the nearest point of b."""
    if len(a) == 0 or len(b) == 0:
        return np.full(len(a), np.inf)
    out = np.empty(len(a))
    for k in range(0, len(a), 2000):
        d = np.hypot(a[k:k + 2000, None, 0] - b[None, :, 0], a[k:k + 2000, None, 1] - b[None, :, 1])
        out[k:k + 2000] = d.min(1)
    return out


def _cells_xy(cells):
    return np.array([rc(i) for i in cells], float)


def score(points, T, tol=TOL):
    """Score normalised points against one image's truth record. Returns a JSON-ready dict."""
    if not points:
        return dict(parse_ok=False, passed=False, precision=0.0, recall=0.0, f1=0.0, failure="no path given")
    F = T["frame"]
    grid = [norm_to_grid(x, y, F) for x, y in points]
    drawn = densify(grid)
    true = densify(_cells_xy(T["path"]))
    lake = set(T["lake_cells"])
    true_dry = densify(_cells_xy([i for i in T["path"] if i not in lake])) if len(lake) else true
    inside = (drawn[:, 0] >= -.5) & (drawn[:, 0] <= N - .5) & (drawn[:, 1] >= -.5) & (drawn[:, 1] <= N - .5)
    cell_of = lambda q: int(round(q[0])) * N + int(round(q[1]))
    in_lake = np.array([ok and cell_of(q) in lake for q, ok in zip(drawn, inside)])
    d_drawn = _nearest(drawn, true)
    on = (d_drawn <= tol) | in_lake
    d_true = _nearest(true_dry, drawn) if len(true_dry) else np.zeros(0)
    curve = {str(t): dict(precision=round(float(((d_drawn <= t) | in_lake).mean()), 4),
                          recall=round(float((d_true <= t).mean()) if len(d_true) else 1.0, 4)) for t in CURVE}
    precision, recall = float(on.mean()), float((d_true <= tol).mean()) if len(d_true) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    # where the off-path parts of the drawn line went
    up, stream = _cells_xy(T["upstream"]), _cells_xy(T["stream"])
    off = ~on
    where = dict(on_path=float(on.mean()), off_map=float((off & ~inside).mean()), upstream=0.0, other_stream=0.0, land=0.0)
    if off.any():
        pts_off = drawn[off & inside]
        if len(pts_off):
            d_up, d_st = _nearest(pts_off, up), _nearest(pts_off, stream)
            k_up = d_up <= 1.5
            k_st = ~k_up & (d_st <= 1.5)
            n = len(drawn)
            where["upstream"] = float(k_up.sum() / n)
            where["other_stream"] = float(k_st.sum() / n)
            where["land"] = float((~k_up & ~k_st).sum() / n)
    O = rc(T["O"])
    start_err = math.dist(grid[0], O)
    end_true = rc(T["path"][-1])
    end_err = math.dist(grid[-1], end_true)
    passed = precision >= PASS and recall >= PASS
    failure = None
    if not passed:
        if start_err > 2 * tol and math.dist(grid[-1], O) < start_err:
            failure = "drawn the wrong way round (ends at O)"
        elif where["upstream"] >= .25:
            failure = "traced upstream, against the flow"
        elif where["off_map"] >= .25:
            failure = "points outside the map"
        elif where["other_stream"] >= max(.2, where["land"]):
            failure = "jumped to another stream"
        elif where["land"] >= .3:
            failure = "cut across dry land"
        elif precision >= PASS and recall < PASS:
            failure = "stopped before the water leaves the area" if end_err > 2 * tol else "skipped part of the route"
        elif start_err > 2 * tol:
            failure = "did not start at outfall O"
        else:
            failure = "strayed from the stream"
    return dict(parse_ok=True, passed=bool(passed), precision=round(precision, 4), recall=round(recall, 4),
                f1=round(f1, 4), n_points=len(points), start_error_cells=round(start_err, 1),
                end_error_cells=round(end_err, 1), where={k: round(v, 4) for k, v in where.items()},
                curve=curve, failure=failure)


# ---------------------------------------------------------------------------------------------------------------------
# reference lines (no model): the scorer's anchors
# ---------------------------------------------------------------------------------------------------------------------
def oracle(T, every=4):
    """The true path itself, sampled every few cells and rounded to whole normalised units: must pass."""
    cells = T["path"][::every] + [T["path"][-1]]
    return [tuple(round(v) for v in cell_to_norm(i, T["frame"])) for i in cells]


def straight_south(T):
    """'Water flows south': a straight line from O to the bottom edge."""
    r, c = rc(T["O"])
    F = T["frame"]
    return [cell_to_norm(T["O"], F), cell_to_norm((N - 1) * N + c, F)]


def straight_to_exit(T):
    """A straight line from O to where the water really leaves the area (knows both ends, ignores the streams)."""
    F = T["frame"]
    return [cell_to_norm(T["O"], F), cell_to_norm(T["path"][-1], F)]
