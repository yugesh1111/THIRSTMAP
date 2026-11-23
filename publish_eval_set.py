"""Publish EXACTLY the tasks and images a results run used, in the dataset's own layout.

Datasets are byte-reproducible on the same platform but can differ slightly across machines
(floating-point and font rendering details), so the evaluation inputs themselves are published:
anyone can re-run the evaluation on identical images with
    python3 evaluate.py --dataset eval_set --all --models ... --run my_rerun
(tasks.jsonl here contains only the evaluated tasks; probes.jsonl / variants.jsonl likewise).

Usage: python3 publish_eval_set.py --dataset dataset --run results/models --out eval_set
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--run", default="results/models")
    ap.add_argument("--out", default="eval_set")
    ap.add_argument("--extra-runs", nargs="*", default=["results/finetune"])
    a = ap.parse_args()
    ds, out = Path(a.dataset), Path(a.out)
    used = set()
    for run in [a.run] + a.extra_runs:
        f = Path(run) / "responses.jsonl"
        if f.exists():
            used |= {json.loads(l)["task_id"] for l in open(f)}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files, counts = set(), {}
    for name in ("tasks.jsonl", "probes.jsonl", "variants.jsonl"):
        src = ds / name
        if not src.exists():
            continue
        keep = [json.loads(l) for l in open(src) if json.loads(l)["task_id"] in used]
        # keep both halves of every counterfactual pair and every appearance group that was used
        with open(out / name, "w") as f:
            for t in keep:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
                files.update({t["image"], t["reveal"]})
                files.add(str(Path(t["image"]).parent / "answer_key.json") if t["image"].startswith("scenes/")
                          else f"scenes/{t['scene_id']}/answer_key.json")
        counts[name] = len(keep)
    for rel in sorted(files):
        if (ds / rel).exists():
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ds / rel, out / rel)
    shutil.copy(ds / "manifest.json", out / "manifest_full_dataset.json")
    if (ds / "errata.jsonl").exists():                  # audit exclusions for the published tasks
        with open(out / "errata.jsonl", "w") as f:
            for line in open(ds / "errata.jsonl"):
                if json.loads(line)["task_id"] in used:
                    f.write(line)
    sums = {rel: hashlib.sha256((out / rel).read_bytes()).hexdigest() for rel in sorted(files) if (out / rel).exists()}
    (out / "SHA256SUMS.json").write_text(json.dumps(sums, indent=1))
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) / 2 ** 20
    (out / "README.md").write_text(f"""# Evaluation set (exact inputs the models saw)

These are **exactly** the tasks and images used for the open-model evaluation in `{a.run}`
(and the fine-tuning test, if present): {", ".join(f"{v} from {k}" for k, v in counts.items())}.
{len(sums)} files, {size:.0f} MB, with SHA-256 checksums in `SHA256SUMS.json`.

Why publish the inputs? The generator is byte-for-byte reproducible on the same platform, but a different
machine (for example a GitHub runner) can produce a slightly different but equally valid dataset because of
floating-point and font-rendering details. Publishing the evaluated images removes that doubt:

```bash
python3 evaluate.py --dataset eval_set --all --models hf:Qwen/Qwen2.5-VL-3B-Instruct --workers 1 --run rerun
python3 evaluate.py --dataset eval_set --all --models hf:Qwen/Qwen2.5-VL-3B-Instruct --workers 1 --blind --run rerun   # + no-image check
```

`--all` asks every task here, including the reading checks (`probes.jsonl`) and the appearance variants
(`variants.jsonl`). `scenes/*/answer_key.json` and the `*_reveal.png` images show the answers for checking by eye.
""")
    print(f"{counts} -> {out}  ({len(sums)} files, {size:.0f} MB)")


if __name__ == "__main__":
    main()
