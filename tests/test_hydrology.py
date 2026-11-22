"""V2: known-answer terrains. If the water simulation is wrong, these fail.

Each terrain has an answer anyone can see without code: water runs downhill
on a tilted plane, gathers in a valley, stays on its side of a ridge, and
spills out of a bowl.
"""
import numpy as np

from thirstmap.terrain import N, accumulate, d8_receivers, priority_flood, rc, trace

rows, cols = np.mgrid[0:N, 0:N].astype(float)


def route(z):
    filled = priority_flood(z)
    rec = d8_receivers(filled)
    return filled, rec, accumulate(filled, rec)


def test_tilted_plane_flows_straight_south():
    z = (N - rows) * 1.0                      # high in the north, low in the south
    _, rec, _ = route(z)
    path = trace(rec, 10 * N + 50)
    assert all(rc(i)[1] == 50 for i in path)  # never leaves its column
    assert rc(path[-1])[0] == N - 1           # leaves at the south edge


def test_v_valley_collects_everything():
    z = np.abs(cols - N // 2) * 2.0 + (N - rows) * 0.5
    _, rec, acc = route(z)
    for start in (5 * N + 5, 5 * N + N - 6, 80 * N + 20):
        path = trace(rec, start)
        assert any(rc(i)[1] == N // 2 for i in path)   # reaches the valley floor
    assert acc.max() >= 0.5 * N * N                    # most of the area drains to one outlet


def test_ridge_keeps_water_on_its_own_side():
    # two valleys (at N/4 and 3N/4) separated by a ridge at N/2
    z = np.abs(np.abs(cols - N / 2) - N / 4) * 2.0 + (N - rows) * 0.3
    _, rec, _ = route(z)
    left = trace(rec, 20 * N + N // 2 - 6)
    right = trace(rec, 20 * N + N // 2 + 6)
    assert all(rc(i)[1] < N // 2 for i in left)
    assert all(rc(i)[1] > N // 2 for i in right)


def test_counterfactual_removing_ridge_changes_answer():
    """V3: the same start point, with and without a ridge, must give different paths."""
    base = (N - rows) * 0.3 + np.abs(cols - N / 4) * 1.0     # one valley on the left
    ridge = np.where(np.abs(cols - N / 2) < 3, 40.0, 0.0)       # wall between start and valley
    start = 20 * N + N // 2 + 10
    with_ridge = trace(route(base + ridge)[1], start)
    without = trace(route(base)[1], start)
    assert all(rc(i)[1] > N // 2 - 3 for i in with_ridge)      # blocked: stays on the right
    assert any(rc(i)[1] < N // 2 - 3 for i in without)         # free: reaches the left valley


def test_bowl_fills_into_lake_and_spills_south():
    z = (N - rows) * 0.2 + 10.0
    bowl = np.hypot(rows - 60, cols - 80) < 15
    z = np.where(bowl, z - 8.0, z)
    filled, rec, _ = route(z)
    lake = (filled - z) > 2.5
    assert lake[60, 80]                                         # the pit became a lake
    assert rc(trace(rec, 60 * N + 80)[-1])[0] == N - 1          # and its water still leaves south


def test_every_cell_drains_out():
    rng = np.random.default_rng(0)
    z = rng.normal(size=(N, N)).cumsum(0) + (N - rows)
    _, rec, acc = route(z)
    outlets = rec == -1
    assert outlets.sum() == N                                   # only the south edge is an outlet
    assert acc[N - 1].sum() == N * N                            # all water leaves through it
