"""The two newest task families: drawing the water's path, and questions a cloud makes unanswerable.

Path scoring is anchored by lines whose verdict is known without any model (the true path passes; straight lines and
upstream traces fail, with the right diagnosis). Every cloud item is re-derived from its scene's seed: the proof that
the hidden version has two answers must come out the same, and the edge-splitting rule is checked on hand-made cases.
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from thirstmap import clouds, paths
from thirstmap.terrain import N, rc

TRACE = Path("eval_set/trace")
CLOUD = Path("eval_set/cloud")
trace_items = [json.loads(l) for l in open(TRACE / "tasks.jsonl")] if (TRACE / "tasks.jsonl").exists() else []
cloud_items = json.loads((CLOUD / "items.json").read_text())["items"] if (CLOUD / "items.json").exists() else []


# ---------------------------------------------------------------------------------------------------------------------
# draw the water's path
# ---------------------------------------------------------------------------------------------------------------------
def test_frames_round_trip():
    F = paths.frame_sat()
    for i in (0, 77 * N + 13, N * N - 1):
        x, y = paths.cell_to_norm(i, F)
        r, c = paths.norm_to_grid(x, y, F)
        assert (round(r), round(c)) == rc(i)


@pytest.mark.skipif(not trace_items, reason="trace set not built")
@pytest.mark.parametrize("it", trace_items, ids=lambda it: it["task_id"])
def test_reference_lines(it):
    T = it["truth"]
    assert paths.score(paths.oracle(T), T)["passed"]                       # the true path, rounded: passes
    rev = paths.oracle(T)[::-1]
    assert paths.score(rev, T)["passed"]                                   # the route is what counts, not the order
    assert not paths.score(paths.straight_south(T), T)["passed"]           # "water flows south" is not a route
    assert paths.score(None, T)["failure"] == "no path given"


@pytest.mark.skipif(not trace_items, reason="trace set not built")
def test_upstream_trace_is_named():
    """A line drawn up the stream that feeds O (against the flow) fails and is called that."""
    for it in trace_items:
        T = it["truth"]
        if len(T["upstream"]) < 30:
            continue
        up = set(T["upstream"])
        r0, c0 = rc(T["O"])
        chain = sorted(up, key=lambda i: math.dist(rc(i), (r0, c0)))[:40]
        line = [paths.cell_to_norm(T["O"], T["frame"])] + [paths.cell_to_norm(i, T["frame"]) for i in chain[::4]]
        sc = paths.score(line, T)
        assert not sc["passed"]
        if sc["where"]["upstream"] >= .25:
            assert sc["failure"] in ("traced upstream, against the flow", "drawn the wrong way round (ends at O)")
            return
    pytest.skip("no image with a long enough stream upstream of O")


def test_parse_formats():
    assert paths.parse('{"path": [{"x": 1, "y": 2}, {"x": 3, "y": 4}], "villages": ["V1"]}') == [(1, 2), (3, 4)]
    assert paths.parse("```json\n{\"path\": [[10, 20], [30, 40]]}\n```") == [(10, 20), (30, 40)]
    assert paths.parse('{"path": [{"x": 5, "y": 6}, {"x": 7, "y": 8}, {"x": 9') == [(5, 6), (7, 8)]   # cut off
    assert paths.parse("I cannot trace this.") is None
    assert paths.parse_villages('{"path": [], "villages": ["V2", "V5"]}') == ["V2", "V5"]


@pytest.mark.skipif(not trace_items, reason="trace set not built")
def test_trace_truth_rebuilds_from_seed():
    """The stored route is the simulation's: rebuild two scenes from their seeds and compare."""
    from thirstmap.rebuild import rebuild
    for it in trace_items[:2]:
        r = rebuild(TRACE, it["scene_id"])
        assert [int(i) for i in r["s"]["path"]] == it["truth"]["path"]
        assert sorted(r["nm"]["village"][v] for v in r["p"]["villages"] if v in set(r["s"]["path"])) == sorted(it["villages_answer"])


# ---------------------------------------------------------------------------------------------------------------------
# can't-tell clouds
# ---------------------------------------------------------------------------------------------------------------------
def _ring(spec):
    """Boundary points on a circle: spec = [(cell_id, angle_degrees)]."""
    return {i: math.radians(a) for i, a in spec}


def test_split_edge_respects_crossing_flow_and_height():
    # exits at 0 deg (x) and 180 deg (j); our entry at 90 deg (e0), another at 270 deg (e1)
    x, j, e0, e1 = 1, 2, 3, 4
    ang = _ring([(x, 0), (j, 180), (e0, 90), (e1, 270)])
    acc = {x: 300, j: 900, e0: 200, e1: 500}
    hi = {x: 10, j: 10, e0: 50, e1: 50}
    acc_a, hi_a = np.zeros(10), np.zeros(10)
    for k, v in acc.items():
        acc_a[k] = v
    for k, v in hi.items():
        hi_a[k] = v
    assert clouds.split_edge([e0, e1], [x, j], ang, acc_a, hi_a, e0, j) is not None          # room for both in j
    acc_a[j] = 600                                                                             # j cannot take e0 + e1 ...
    world = clouds.split_edge([e0, e1], [x, j], ang, acc_a, hi_a, e0, j)
    assert world is None or world[e1] == x                                                     # ... unless e1 goes to x
    acc_a[x] = 100                                                                             # and x is too small for e1
    assert clouds.split_edge([e0, e1], [x, j], ang, acc_a, hi_a, e0, j) is None
    acc_a[x], acc_a[j] = 300, 900
    hi_a[j] = 60                                                                               # j higher than e0: uphill
    assert clouds.split_edge([e0, e1], [x, j], ang, acc_a, hi_a, e0, j) is None


def test_split_edge_never_crosses():
    # order round the circle: e0 (10 deg), x (90), e1 (170), j (250): e0 -> j forces e1 into x's or j's stretch
    # without crossing; e0 and e1 swapped exits (e0 -> j, e1 -> x would cross only if x lay between them on j's side)
    e0, x, e1, j = 1, 2, 3, 4
    ang = _ring([(e0, 10), (x, 90), (e1, 170), (j, 250)])
    acc_a, hi_a = np.full(5, 1000.0), np.zeros(5)
    hi_a[e0] = hi_a[e1] = 50
    acc_a[e0], acc_a[e1] = 10, 10
    world = clouds.split_edge([e0, e1], [x, j], ang, acc_a, hi_a, e0, j)
    assert world is not None and world[e0] == j
    # with x's stretch forced to contain e0 by a third exit between e0 and j, e0 -> j becomes impossible
    k = 5
    acc_a = np.append(acc_a, 1000.0)
    hi_a = np.append(hi_a, 0.0)
    ang2 = _ring([(e0, 10), (x, 90), (e1, 170), (j, 250), (k, 330)])
    w2 = clouds.split_edge([e0, e1], [x, j, k], ang2, acc_a, hi_a, e0, j)
    assert w2 is None                                                                         # k sits between e0 and j


@pytest.mark.skipif(not cloud_items, reason="cloud set not built")
@pytest.mark.parametrize("it", cloud_items, ids=lambda it: it["scene_id"])
def test_cloud_items_checks(it):
    assert all(it["checks"].values()), it["checks"]
    assert it["hidden"]["alternatives"]
    for alt in it["hidden"]["alternatives"]:
        assert sorted(alt["villages"]) != sorted(it["truth"])


@pytest.mark.skipif(not cloud_items, reason="cloud set not built")
def test_cloud_proof_rederived_from_seed():
    """Rebuild scenes from their seeds and re-run the proof: the same exits, the same alternatives."""
    from thirstmap.rebuild import rebuild
    for it in cloud_items[:3]:
        r = rebuild(CLOUD, it["scene_id"])
        a = clouds.analyse(r["s"], r["p"], it["hidden"]["center"], it["hidden"]["R"])
        lab = lambda vs: sorted(r["nm"]["village"][v] for v in vs)
        assert lab(a["truth"]) == it["truth"]
        assert [x["exit"] for x in a["alternatives"]] == [x["exit"] for x in it["hidden"]["alternatives"]]
        assert [lab(x["answer"]) for x in a["alternatives"]] == [x["villages"] for x in it["hidden"]["alternatives"]]


def test_cloud_core_is_opaque():
    a = clouds.cloud_alpha(80 * N + 80, 6, seed=3)
    yy, xx = np.mgrid[0:800, 0:800]
    core = np.hypot(xx - 402.5, yy - 402.5) <= (6 + clouds.BAND) * 5
    assert a[core].min() == 1.0
    assert a[np.hypot(xx - 402.5, yy - 402.5) > clouds.outer_px(6) + 1].max() == 0.0


def test_cloud_scoring():
    from cloud_task import score
    t = dict(variant="hidden", truth=["V1", "V3"], options=["V1", "V2", "V3"], alternatives=[["V3"]])
    assert score(t, '{"answer": "cannot be determined"}')["correct"]
    assert score(t, "The cloud hides the stream, so it cannot be determined.")["abstained"]
    assert score(t, '{"answer": ["V1", "V3"]}')["kind"] == "the hidden truth"
    assert score(t, '{"answer": ["V3"]}')["kind"] == "an alternative the cloud allows"
    d = dict(t, variant="decoy")
    assert score(d, '{"answer": ["V3", "V1"]}')["correct"]
    assert not score(d, '{"answer": "cannot be determined"}')["correct"]
