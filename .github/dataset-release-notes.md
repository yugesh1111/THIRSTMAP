Full ThirstMap benchmark dataset, **regenerated from the code on GitHub's own runners** by the
`dataset-release` workflow (same seeds, locked library versions in `requirements-lock.txt`).

| File | Contents |
|---|---|
| `thirstmap-dataset-part1-levels1-3.zip` | synthetic scenes, difficulty 1-3 (+ counterfactual twins) |
| `thirstmap-dataset-part2-levels4-5.zip` | synthetic scenes, difficulty 4-5 (+ twins) |
| `thirstmap-dataset-part3-real-terrain.zip` | real terrain: Navi Mumbai, Hyderabad, Pune, Chennai (+ twins) |
| `manifest.json` | counts, validator pass rates, dropped questions, answer balance |
| `VALIDATION_REPORT.md`, `VERIFICATION.md` | validation evidence and independent verification of this build |
| `SHA256SUMS.txt` | checksums: `sha256sum -c SHA256SUMS.txt` |

Each zip is self-contained (includes `dataset/tasks.jsonl` and `dataset/manifest.json`). Unzip all three into the
repository root to recreate `dataset/`, then for example:

```bash
python3 evaluate.py --dataset dataset --per-cell 3 --blind --run my_run --models mock:oracle mock:random
```

Real-terrain data credits: Copernicus DEM GLO-30 (modified), ESA WorldCover 2021 (CC BY 4.0).
Facilities placed on real terrain are hypothetical.
