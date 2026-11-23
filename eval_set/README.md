# Evaluation set (exact inputs the models saw)

These are **exactly** the tasks and images used for the open-model evaluation in `results/open_models`
(and the fine-tuning test, if present): 168 from tasks.jsonl, 16 from probes.jsonl, 72 from variants.jsonl.
543 files, 330 MB, with SHA-256 checksums in `SHA256SUMS.json`.

Why publish the inputs? The generator is byte-for-byte reproducible on the same platform, but a different
machine (for example a GitHub runner) can produce a slightly different but equally valid dataset because of
floating-point and font-rendering details. Publishing the evaluated images removes that doubt:

```bash
python3 evaluate.py --dataset eval_set --all --models hf:Qwen/Qwen2.5-VL-3B-Instruct --workers 1 --run rerun
python3 evaluate.py --dataset eval_set --all --models hf:Qwen/Qwen2.5-VL-3B-Instruct --workers 1 --blind --run rerun   # + no-image check
```

`--all` asks every task here, including the reading checks (`probes.jsonl`) and the appearance variants
(`variants.jsonl`). `scenes/*/answer_key.json` and the `*_reveal.png` images show the answers for checking by eye.
