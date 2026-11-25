"""The leaderboard page scores replies in the browser with docs/leaderboard/score.js. It must give exactly the verdict
the Python scorer gives, on every published reply."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from thirstmap.scoring import score

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs/leaderboard/data.json"

JS = r"""
const S = require(process.argv[2]), d = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const T = Object.fromEntries(d.tasks.map(t => [t.task_id, t]));
process.stdout.write(JSON.stringify(d.rows.map(([id, raw]) => { const s = S.score(T[id], raw); return [s.correct, s.parsed, s.credit, s.tags]; })));
"""


@pytest.mark.skipif(not shutil.which("node") or not DATA.exists(), reason="needs node and the built leaderboard")
def test_browser_scorer_matches_python_on_every_published_reply(tmp_path):
    d = json.loads(DATA.read_text())
    tasks = {t["task_id"]: t for t in d["tasks"]}
    rows = [(tid, raw) for m in d["models"] for replies in m["replies"].values() for tid, raw in replies.items()]
    edge = ['{"answer": "south-west"}', '```json\n{"answer": ["V1", "v2"]}\n```', 'I think V3 and V4.', '{"answer": 1e3}',
            '{"answer": ["SE"]}', '{"answer": null}', 'none', '{"answer": 100000000000000000000000000000000000000000}']
    rows += [(tid, raw) for tid in list(tasks)[:40] for raw in edge]
    assert len(rows) > 500
    script = tmp_path / "parity.js"
    script.write_text(JS)
    out = subprocess.run(["node", str(script), str(ROOT / "docs/leaderboard/score.js")], input=json.dumps(dict(tasks=d["tasks"], rows=rows)),
                         capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    py = [[s["correct"], s["parsed"], s["credit"], s["tags"]] for s in (score(tasks[tid], raw) for tid, raw in rows)]
    def num(x):                                       # 1.0 (Python) and 1 (JavaScript) are the same number
        return [num(v) for v in x] if isinstance(x, list) else float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x
    diff = [(rows[i], py[i], js[i]) for i in range(len(rows)) if num(py[i]) != num(js[i])]
    assert not diff, diff[:3]
