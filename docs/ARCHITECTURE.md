# ThirstMap — architecture

```mermaid
flowchart LR
  subgraph GEN["1 · Generate (no model involved)"]
    T["terrain.py<br/>fractal terrain or real Copernicus DEM<br/>priority-flood + D8 routing"] --> S["scene.py<br/>data centre, outfall, villages + traps,<br/>wetlands, sites, intake, heat plume"]
    S --> Q["questions.py<br/>10 question types<br/>answer key, options, traps"]
    S --> CF["counterfactual.py<br/>twin with one minimal change"]
    S --> R["render_sat / render_map / render_thermal<br/>3 image styles + answer reveals"]
    R --> AV["variants.py<br/>monsoon · haze · coarse sensor<br/>(answer must NOT change)"]
    R --> PR["probes.py<br/>reading checks: labels, heights"]
  end
  subgraph VAL["2 · Validate (drop, never edit)"]
    V1["V1 pysheds recomputes every answer"]
    V9["V9 answer visible in rendered pixels"]
    VM["V5/V7/V8 margins · V10 labels · V11 styles"]
  end
  subgraph EVAL["3 · Evaluate"]
    E["evaluate.py<br/>Claude / OpenAI-compatible / Gemini<br/>Hugging Face open models (hf:)<br/>+ oracle / random / stubborn baselines<br/>with and without the image"]
    FT["finetune.py<br/>LoRA on held-out scenes:<br/>can the data teach the skill?"]
    ST["staircase.py<br/>adaptive eye exam"]
    H["human_eval.py<br/>human baseline"]
  end
  subgraph OUT["4 · Evidence"]
    REP["report.py: skills vs exact chance (binomial test),<br/>breaking levels, map vs satellite, pairs,<br/>appearance invariance, probes, traps, cost"]
    FI["findings.py: README + FINDINGS.md<br/>straight from summary.json"]
    ES["publish_eval_set.py: exact evaluated<br/>images + SHA-256"]
    VER["verify_results.py: independent recompute,<br/>second parser on real replies, chance check,<br/>byte-identical regeneration"]
    VR["validation_report.py"]
    D["build_demo.py: ✓/✗ demo page"]
  end
  Q --> VAL
  R --> VAL
  CF --> VAL
  VAL -->|kept tasks| B["build_dataset.py<br/>tasks.jsonl + manifest"]
  AV --> B
  PR --> B
  B --> E --> REP --> FI
  E --> ES
  B --> FT --> REP
  B --> ST
  B --> H
  E --> D
  E --> VER
  B --> VR
```

## Data flow in one sentence
A **scene script** (terrain + simulated water + placements) is the single source of truth. Every image is *rendered from* it, every answer is *computed from* it, an *independent library* recomputes the answers, the *rendered pixels* are checked to contain the evidence, and only then is a task released to models.

## Key design decisions
| Decision | Why |
|---|---|
| Answers come from a simulation, not from labels | Exact, reproducible, and nobody can argue with the ground truth |
| Three image styles share one answer key | Separates "understands the land" from "reads map symbols" |
| Drop, never edit | Prevents hand-tuning the benchmark toward a result |
| Independent re-implementation (pysheds) | A bug in our routing can't silently become a "correct" answer |
| Pixel-level evidence checks | "The answer is in the data" is not enough; it must be *visible* |
| Traps and counterfactual twins | Wrong answers are diagnosed, and answering from habit is exposed |
| Balanced answer positions | No "always pick S3" shortcut |
| Adaptive 2-down/1-up exam | Locates breaking points with ~144 calls per model instead of ~2,000 |
| Real-terrain mode | Shows the synthetic findings transfer to real Indian geography |
| Chance computed per task, binomial test | "16%" means nothing without knowing that guessing gives 13% |
| Reading checks (probes) | Separates "cannot see the label" from "cannot reason about the water" |
| Appearance variants | Season, haze and sensor resolution must not change a correct answer |
| Raw replies are the source of truth | The report and demo re-score every raw reply; a second parser re-checks them |
| Publish the exact evaluated inputs | Dataset builds can differ slightly across machines; `eval_set/` removes the doubt |

## Repeatability
- Same seed gives byte-identical images and answers (tested; `verify_results.py` regenerates dataset samples).
- `.github/workflows/ci.yml` (and `.gitlab-ci.yml`) run the tests and a small end-to-end build on every push; `dataset-release.yml` rebuilds the full dataset on GitHub's runners.
- Across machines, floating-point and font details can change a few scenes, so the images the models actually saw are published in `eval_set/` with checksums.
- One command per stage (see README *Quick start*).
