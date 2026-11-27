"""Run ./run_all.sh --quick and record every output line with the seconds since the start (for the step 0 GIF).

    python video/walkthrough/time_quick_run.py <copy-of-the-repo> quick_log.json

Run it in a copy (e.g. `git archive HEAD | tar -x -C /tmp/tm`): the quick run rewrites demo/, human_eval/ and
docs/VALIDATION_REPORT.md in the folder it runs in.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

repo, out = Path(sys.argv[1]), Path(sys.argv[2])
t0, lines = time.time(), []
p = subprocess.Popen(["bash", "-c", "./run_all.sh --quick 2>&1"], cwd=repo, stdout=subprocess.PIPE, text=True, bufsize=1)
for line in p.stdout:
    lines.append([round(time.time() - t0, 2), line.rstrip("\n")])
    print(line, end="", flush=True)
p.wait()
lines.append([round(time.time() - t0, 2), None])
out.write_text(json.dumps({"rc": p.returncode, "lines": lines}, indent=0))
