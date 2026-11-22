"""Every task in the built dataset must point at real files and carry a complete record."""
import json
from pathlib import Path

import pytest

DS = Path(__file__).resolve().parent.parent / "dataset"


@pytest.mark.skipif(not (DS / "tasks.jsonl").exists(), reason="dataset not built")
def test_task_records_are_complete_and_images_exist():
    tasks = [json.loads(l) for l in open(DS / "tasks.jsonl")]
    assert tasks
    for t in tasks:
        assert (DS / t["image"]).is_file(), t["image"]
        assert (DS / t["reveal"]).is_file(), t["reveal"]
        assert t["options"] and t["prompt"] and t["scoring"] in ("set", "choice", "compass", "number")
        assert t["answer"] is not None
        if t["scoring"] in ("choice", "compass"):
            assert t["answer"] in t["options"]
        if t["scoring"] == "set":
            assert set(t["answer"]) <= set(map(str, t["options"]))


@pytest.mark.skipif(not (DS / "tasks.jsonl").exists(), reason="dataset not built")
def test_counterfactual_pairs_are_linked_and_flip():
    tasks = [json.loads(l) for l in open(DS / "tasks.jsonl")]
    pairs = {}
    for t in tasks:
        if t.get("pair_id"):
            pairs.setdefault(t["pair_id"], {})[t["variant"]] = t
    assert pairs, "no counterfactual pairs in the dataset"
    for pid, v in pairs.items():
        assert set(v) == {"base", "counterfactual"}, pid
        b, c = v["base"], v["counterfactual"]
        assert b["qid"] == c["qid"] and b["style"] == c["style"] and b["level"] == c["level"]
        assert b["answer"] != c["answer"] and c["pair_answer"] == b["answer"]
        assert b["image"] != c["image"]
