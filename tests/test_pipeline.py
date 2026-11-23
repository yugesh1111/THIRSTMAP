"""Pipeline-level checks: determinism (V4), answer-key properties, validators on many scenes."""
import hashlib
import json

import numpy as np
import pytest

from generate import generate
from thirstmap.questions import answer_key
from thirstmap.scene import make
from thirstmap.terrain import params, trace
from thirstmap.validate import independent_answers


def _digest(folder):
    h = hashlib.sha256()
    for name in sorted(p.name for p in folder.iterdir()):
        h.update(name.encode())
        h.update((folder / name).read_bytes())
    return h.hexdigest()


def test_same_seed_gives_identical_outputs(tmp_path):
    a, _, _ = generate(3, 101, tmp_path / "a")
    b, _, _ = generate(3, 101, tmp_path / "b")
    assert json.loads((a / "answer_key.json").read_text()) == json.loads((b / "answer_key.json").read_text())
    assert _digest(a) == _digest(b)


@pytest.mark.parametrize("level,seed", [(1, 3), (2, 8), (3, 21), (4, 34), (5, 55)])
def test_answer_key_properties(level, seed):
    s, p = make(seed, params(level))
    qs, nm, truth = answer_key(s, p)
    key = {q["id"]: q["answer"] for q in qs}
    path = set(s["path"])
    # Q1: answer villages are exactly those on the wastewater path
    assert key["Q1"] == sorted(nm["village"][v] for v in p["villages"] if v in path)
    # Q3: the correct wetland is on the path; the 'too late' one (if any) is after a village
    assert p["good"] in path
    # Q6: the clean site's wastewater meets no village; the others meet at least one
    sit = p.get("siting")
    if sit:
        for site, o in zip(sit["sites"], sit["site_outfalls"]):
            met = set(trace(s["rec"], o)) & set(p["villages"])
            assert (not met) == (site == sit["clean_site"])
    # Q7: every listed village drains through intake I, no unlisted one does
    itk = p.get("intake")
    if itk:
        for v in p["villages"]:
            assert (itk["intake"] in trace(s["rec"], v)) == (v in itk["upstream"])


@pytest.mark.parametrize("level,seed", [(1, 4), (3, 12), (5, 77)])
def test_independent_implementation_agrees(level, seed):
    s, p = make(seed, params(level))
    qs, nm, _ = answer_key(s, p)
    ind, agree = independent_answers(s, p, nm, qs)
    assert agree > 0.99
    for q in qs:
        if q["id"] == "Q9":
            assert abs(q["answer"] - ind["Q9"]) <= 0.3
        elif q["id"] == "Q10":
            assert abs(q["answer"] - ind["Q10"]) <= 0.05 * q["answer"]
        else:
            assert q["answer"] == ind[q["id"]], q["id"]


def test_generated_scene_passes_validation(tmp_path):
    out, kept, report = generate(4, 202, tmp_path)
    assert report["scene_ok"]
    assert report["checks"]["V1_independent_pysheds"]["passed"]
    assert len(kept) >= 5
    for name in ("satellite.png", "map.png", "answer_key.json", "validation.json"):
        assert (out / name).exists()
