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
