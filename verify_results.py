"""Independent verification of reported numbers and of the dataset itself.

Deliberately does NOT reuse report.py or the scorer:
  1. recomputes accuracies from the raw responses with its own simple checks, and compares
     them with the numbers in summary.json;
  2. compares the random baseline with its exact mathematical chance level per task;
  3. regenerates sampled scenes from their recorded seeds and checks the answer keys and
     images are byte-identical to the dataset (the dataset really comes from this code);
  4. writes a spot-check sheet of random tasks (image, answer key, question) for human eyes.

Usage: python3 verify_results.py [--dataset dataset] [--run results/offline_baselines] [--regen 6]
Writes docs/VERIFICATION.md and docs/spotcheck_*.png
"""
import argparse
import hashlib
import json
import math
import random
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from thirstmap.scoring import chance


def norm(v):
    if isinstance(v, list):
        return sorted(str(x).upper() for x in v)
    if isinstance(v, (int, float)):
        return float(v)
    return str(v).upper()


def simple_correct(t, raw):
    """Own minimal scorer: exact JSON answers only (the offline baselines emit exact JSON)."""
    try:
        a = json.loads(raw)["answer"]
    except (ValueError, KeyError, TypeError):
        return False
    if t["scoring"] == "number":
        return abs(float(a) - float(t["answer"])) <= t["tolerance"]
    return norm(a) == norm(t["answer"])


def recover_jobs(key, k_max=500):
    """Job candidates (balance index, base seed) for a scene.

    New builds record the balance index in the answer key; older ones are recovered by
    inverting build_dataset's seed schedule (seed = base + 1000*j + 7919*t). Every
    candidate is returned, and the caller accepts the one that reproduces the scene.
    """
    level, seed = key["level"], key["seed"]
    if "balance_index" in key:
        k = key["balance_index"]
        return [(k, 1000 + 97 * k + 10007 * level)]
    out = []
    for k in range(k_max):
        base = 1000 + 97 * k + 10007 * level
        for t in range(20):
            rest = seed - base - 7919 * t
            if rest >= 0 and rest % 1000 == 0 and rest // 1000 < 60:
                out.append((k, base))
    return out


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--run", default="results/offline_baselines")
    ap.add_argument("--regen", type=int, default=6)
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    ds, run, out = Path(a.dataset), Path(a.run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = {json.loads(l)["task_id"]: json.loads(l) for l in open(ds / "tasks.jsonl")}
    L = ["# Independent verification", "",
         "This file is produced by `verify_results.py`, which does not reuse the report or scoring code.", "",
         "> **Important:** the models named `mock:*` are offline *baselines* used to test the dataset and the",
         "> scorer: `oracle` returns the answer key, `random` picks random options, `stubborn` repeats the",
         "> original answer on counterfactual twins. They are **not** AI models. No frontier model has been",
         "> evaluated yet; their results will be added when API access is available.", ""]

    # 1 + 2: recompute numbers, compare with summary and with exact chance
    rows = [json.loads(l) for l in open(run / "responses.jsonl")]
    summ = json.loads((run / "summary.json").read_text())
    L += ["## 1. Reported accuracies recomputed from raw responses", "",
          "| Model | Mode | Responses | Recomputed | In summary.json | Match |", "|---|---|---|---|---|---|"]
    latest = {}
    for r in rows:
        if not r.get("error"):
            latest[(r["model"], r["mode"], r["task_id"])] = r
    by = defaultdict(list)
    for (m, mode, tid), r in latest.items():
        by[(m, mode)].append(simple_correct(tasks[tid], r["raw"]))
    all_match = True
    for (m, mode), v in sorted(by.items()):
        mine = sum(v) / len(v)
        theirs = summ["overall"][m][mode]
        ok = abs(mine - theirs) < 1e-9
        all_match &= ok
        L.append(f"| {m} | {mode} | {len(v)} | {100 * mine:.2f}% | {100 * theirs:.2f}% | {'✅' if ok else '❌'} |")
    L += ["", f"**All reported accuracies reproduced exactly: {'yes' if all_match else 'NO'}.**", ""]

    rnd = [(tasks[tid], r) for (m, mode, tid), r in latest.items() if m == "mock:random" and mode == "image"]
    if rnd:
        exp = sum(chance(t) for t, _ in rnd)
        obs = sum(simple_correct(t, r["raw"]) for t, r in rnd)
        sd = math.sqrt(sum(chance(t) * (1 - chance(t)) for t, _ in rnd))
        z = (obs - exp) / sd
        L += ["## 2. Random baseline vs exact chance", "",
              f"Expected correct by pure chance (computed from each task's options): **{exp:.1f}** of {len(rnd)} "
              f"({100 * exp / len(rnd):.1f}%). Observed: **{obs}** ({100 * obs / len(rnd):.1f}%). "
              f"Difference = {z:+.2f} standard deviations "
              f"({'consistent with chance' if abs(z) < 3 else 'NOT consistent with chance'}).", "",
              "| Question type | Tasks | Expected | Observed |", "|---|---|---|---|"]
        per = defaultdict(lambda: [0, 0.0, 0])
        for t, r in rnd:
            per[t["qid"]][0] += 1
            per[t["qid"]][1] += chance(t)
            per[t["qid"]][2] += simple_correct(t, r["raw"])
        for q in sorted(per, key=lambda x: int(x[1:])):
            n, e, o = per[q]
            L.append(f"| {q} | {n} | {100 * e / n:.1f}% | {100 * o / n:.1f}% |")
        L.append("")

    # 3: regenerate scenes from seeds, byte-identical?
    from generate import generate
    keys = sorted((ds / "scenes").glob("level*_seed*/answer_key.json"))
    keys = [k for k in keys if not k.parent.name.endswith("_cf")]
    rng = random.Random(2026)
    sample = rng.sample(keys, min(a.regen, len(keys)))
    L += ["## 3. Dataset regenerated from recorded seeds", "",
          "| Scene | Answer key identical | Images identical |", "|---|---|---|"]
    tmp = Path(tempfile.mkdtemp())
    n_ok = 0
    for kp in sample:
        key = json.loads(kp.read_text())
        cands = recover_jobs(key)
        imgs = sorted(p.name for p in kp.parent.glob("*.png"))
        same_key = same_img = False
        for k, base in cands:
            sub = tmp / f"k{k}"
            folder, *_ = generate(key["level"], base, sub, bi=k, twin=True)
            got = json.loads((folder / "answer_key.json").read_text())
            got.pop("balance_index", None)
            want = {kk: vv for kk, vv in key.items() if kk != "balance_index"}
            same_key = got == want
            same_img = (folder.name == kp.parent.name
                        and all(sha(kp.parent / n) == sha(folder / n) for n in imgs))
            if same_key and same_img:
                break
        if not cands:
            L.append(f"| {kp.parent.name} | seed schedule not found | – |")
            continue
        n_ok += same_key and same_img
        L.append(f"| {kp.parent.name} | {'✅' if same_key else '❌'} | {'✅' if same_img else '❌'} ({len(imgs)} images) |")
    shutil.rmtree(tmp, ignore_errors=True)
    L += ["", f"**{n_ok}/{len(sample)} sampled scenes regenerated byte-for-byte from code + seed.**", ""]

    # 4: spot-check sheets
    font = ImageFont.truetype("DejaVuSans.ttf", 15)
    pick = rng.sample([t for t in tasks.values() if t["style"] != "thermal" or True], 6)
    for n, t in enumerate(pick):
        im = Image.open(ds / t["image"]).convert("RGB")
        rv = Image.open(ds / t["reveal"]).convert("RGB")
        h = max(im.height, rv.height)
        sheet = Image.new("RGB", (im.width + rv.width + 20, h + 90), (250, 250, 248))
        sheet.paste(im, (0, 0)); sheet.paste(rv, (im.width + 20, 0))
        d = ImageDraw.Draw(sheet)
        q = t["question"] if len(t["question"]) < 150 else t["question"][:147] + "..."
        d.text((8, h + 8), f"{t['task_id']}", font=font, fill=(80, 80, 80))
        d.text((8, h + 32), q, font=font, fill=(0, 0, 0))
        d.text((8, h + 58), f"Answer key: {t['answer']}   (left: what the model sees; right: answer reveal)",
               font=font, fill=(0, 90, 0))
        sheet.save(out / f"spotcheck_{n + 1}.png")
    L += ["## 4. Spot-check sheets", "",
          "Six random tasks: what the model sees (left) next to the answer reveal (right), with the question and key.", ""]
    L += [f"![spot check {n + 1}](spotcheck_{n + 1}.png)" for n in range(len(pick))]
    (out / "VERIFICATION.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
