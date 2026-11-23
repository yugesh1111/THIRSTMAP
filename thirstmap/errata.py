"""Tasks excluded by a dataset audit (e.g. check V10b, see docs/AUDIT.md). Every score leaves them out."""
import json
from pathlib import Path


def load(dataset):
    path = Path(dataset) / "errata.jsonl"
    if not path.exists():
        return set()
    return {json.loads(line)["task_id"] for line in open(path) if line.strip()}
