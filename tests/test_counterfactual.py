"""Counterfactual twins: exactly one thing changes, and the relevant answers flip."""
import pytest

from thirstmap.counterfactual import KINDS, make_twin
from thirstmap.questions import answer_key
from thirstmap.scene import make
from thirstmap.terrain import params
from thirstmap.validate import independent_answers


@pytest.mark.parametrize("seed", [11, 23, 42, 77])
@pytest.mark.parametrize("kind", KINDS)
def test_twin_changes_one_thing_and_flips_answers(seed, kind):
    P = params(3)
    s, p = make(seed, P)
    qs, nm, _ = answer_key(s, p)
    made = make_twin(s, p, P, kind, qs)
    if made is None:
        pytest.skip(f"no {kind} twin possible for this scene")
    s2, p2, qids, change = made
    # the landscape and every label stay identical
    assert s2["z"] is s["z"] and s2["rec"] is s["rec"]
    assert p2["villages"] == p["villages"] and p2["village_pos"] == p["village_pos"]
    qs2, nm2, _ = answer_key(s2, p2)
    assert nm2["village"] == nm["village"]
    base = {q["id"]: q["answer"] for q in qs}
    twin = {q["id"]: q["answer"] for q in qs2}
    # at least one targeted answer flips (Q2/Q9 may coincide, Q1/Q7/Q8 are required to differ)
    flipped = [q for q in qids if q in base and q in twin and base[q] != twin[q]]
    assert flipped, (kind, base, twin)
    # only the intended thing moved
    if kind == "outfall":
        assert s2["O"] != s["O"] and p2.get("intake") == p.get("intake")
    if kind == "intake":
        assert s2["O"] == s["O"] and p2["intake"]["intake"] != p["intake"]["intake"]
    if kind == "thermal":
        assert s2["O"] == s["O"] and p2["plume"]["points"] == p["plume"]["points"]
    # the independent implementation agrees on the twin's answers
    ind, _ = independent_answers(s2, p2, nm2, qs2)
    for q in qids:
        if q in twin and q != "Q9":
            assert ind[q] == twin[q]
