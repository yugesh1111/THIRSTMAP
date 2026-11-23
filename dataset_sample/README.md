# ThirstMap dataset sample

A ready-to-use slice of the full benchmark, in exactly the same format:

- **28 scenes** (4 per difficulty level 1-5, plus 2 each on real terrain in Navi Mumbai, Hyderabad, Pune and Chennai), plus their counterfactual twins: **56 scene folders**
- **529 tasks** in `tasks.jsonl`, including **69 counterfactual pairs**
- each scene folder: `satellite.png`, `map.png`, `thermal.png` (when present), their `*_reveal.png` answer overlays, `answer_key.json`, `validation.json`

Evaluate on it directly:

```bash
python3 evaluate.py --dataset dataset_sample --models mock:oracle mock:random --blind --run sample_check
```

The **full dataset** (308 scenes, 5,761 tasks, 740 pairs, 2.1 GB) is published by the `dataset-release` GitHub workflow as a Release with three zip parts
(levels 1-3, levels 4-5, real terrain) with SHA-256 checksums, and can also be regenerated exactly with `./run_all.sh`.
`manifest_full_dataset.json` describes the full dataset (counts, validator pass rates, dropped questions, answer balance).
