"""Perception probes: can a model even SEE and READ the image? (no reasoning needed)

Separates "could not read the picture" from "could not reason about it". Built from the
existing scenes and answer keys, so the answers are exact:
  P1 read every village label (V1, V2, ...)            satellite, map
  P2 read the spot height printed next to pond P (m)   map
  P3 read every monitoring point label (M1-M4)         thermal

Usage: python3 probes.py --dataset dataset   -> dataset/probes.jsonl
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from thirstmap.dataset import prompt_for

PROBES = {
    "P1": ("probe_read_labels", "set",
           "Reading check: list EVERY village label (V1, V2, ...) that is written on the image. List all."),
    "P2": ("probe_read_number", "number",
           "Reading check: what spot height, in metres, is written next to the treated-water pond P?"),
    "P3": ("probe_read_labels", "set",
           "Reading check: list EVERY monitoring point label (M1, M2, ...) that is written on the image. List all."),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    a = ap.parse_args()
    ds = Path(a.dataset)
    by_scene = defaultdict(dict)
    for line in open(ds / "tasks.jsonl"):
        t = json.loads(line)
        if t.get("variant") != "counterfactual":
            by_scene[t["scene_id"]].setdefault(t["qid"], {})[t["style"]] = t
    drain_of = {}
    for scene in by_scene:
        key = json.loads((ds / "scenes" / scene / "answer_key.json").read_text())
        drain_of[scene] = key.get("drain_note", "Streams drain off the southern edge.")
    out = []

    def add(scene, qid, style, ref, answer, tolerance=None, options=None):
        skill, scoring, question = PROBES[qid]
        out.append(dict(task_id=f"{scene}__{qid}__{style}", scene_id=scene, level=ref["level"], qid=qid,
                        skill=skill, style=style, image=ref["image"], reveal=ref["reveal"], question=question,
                        terrain=ref["terrain"], prompt=prompt_for(question, style, scoring, drain_of[scene]),
                        scoring=scoring, answer=answer, tolerance=tolerance, options=options, traps={},
                        probe=True))

    for scene, qs in sorted(by_scene.items()):
        q1 = qs.get("Q1", {})
        for style in ("satellite", "map"):
            if style in q1:
                add(scene, "P1", style, q1[style], q1[style]["options"], options=q1[style]["options"])
        q4 = qs.get("Q4", {}).get("map")
        if q4:
            m = re.search(r"spot height (\d+) m", q4["question"])
            if m:
                add(scene, "P2", "map", q4, float(m.group(1)), tolerance=0.5, options=[0, 1000])
        q8 = qs.get("Q8", {}).get("thermal")
        if q8:
            add(scene, "P3", "thermal", q8, q8["options"], options=q8["options"])
    with open(ds / "probes.jsonl", "w") as f:
        for t in out:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"{len(out)} probes -> {ds / 'probes.jsonl'}")


if __name__ == "__main__":
    main()
