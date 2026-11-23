# ThirstMap — can AI trace water through the landscape?

*Innodata AI Hackathon 2026 · Track 2: Visual Task Factory*

> **AI is drinking India's water. We test whether AI can even see where that water goes.**

India's data centres use an estimated ~150 billion litres of water a year, and that could reach ~358 billion by 2030. About 70% of capacity sits in water-stressed Mumbai and Chennai, and none of India's state data-centre policies require water-impact mapping. AI geospatial agents are being built to answer exactly these questions from imagery: *Where does this facility's warm wastewater go? Which villages receive it? Where could a wetland clean it?*

**ThirstMap is a factory of visual tasks** that tests whether frontier multimodal models can be trusted with that job. Our code builds each landscape and simulates its water, so **it already knows every answer**, much like the brief's bar-chart example but for terrain and water flow.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the pipeline diagram and design decisions, and [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) for the full problem statement, sources, and a line-by-line fit to the Track 2 brief.

---

<!-- FINDINGS:START -->
## Findings (open models, real runs)

| Model | Size | Accuracy | Without image | Chance | p (beats chance) | Pair accuracy | Same answer to original & twin | Same answer in 4 looks | Reading checks |
|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-VL-3B-Instruct | 3B | **16%** (23/144) | 13% | 13% | 0.18 | 0% | 87% | 75% (n=24) | 69% (n=16) |
| SmolVLM2-2.2B-Instruct | 2.2B | **8%** (12/144) | 12% | 13% | 0.97 | 0% | 77% | – | 69% (n=16) |
| Qwen2-VL-2B-Instruct | 2B | **8%** (12/144) | 9% | 13% | 0.97 | 0% | 87% | 88% (n=24) | 94% (n=16) |
| SmolVLM-256M-Instruct | 0.26B | **8%** (11/144) | 10% | 13% | 0.99 | 0% | 73% | – | 0% (n=16) |

### What the numbers say

- **No open model is significantly better than random guessing overall** (all p ≥ 0.05). The best, Qwen2.5-VL-3B-Instruct, scores 16% against a chance level of 13% (p = 0.18).
- **The image barely helps.** Accuracy with vs without the image: Qwen2.5-VL-3B-Instruct 16% vs 13%; SmolVLM2-2.2B-Instruct 8% vs 12%; Qwen2-VL-2B-Instruct 8% vs 9%; SmolVLM-256M-Instruct 8% vs 10%.
- **Counterfactual twins expose answering from habit.** Share of pairs where the model gave the same answer to the original and to its twin (whose correct answer is different): Qwen2.5-VL-3B-Instruct 87% (both right: 0%); SmolVLM2-2.2B-Instruct 77% (both right: 0%); Qwen2-VL-2B-Instruct 87% (both right: 0%); SmolVLM-256M-Instruct 73% (both right: 0%).
- **Appearance changes move answers.** Share of question groups answered identically in the dry-season, monsoon, haze and coarse-sensor versions of the same scene (the correct answer is identical in all four): Qwen2.5-VL-3B-Instruct 75%; Qwen2-VL-2B-Instruct 88%.
- **Can they read the image at all?** Reading checks need no reasoning: list every village or monitoring-point label written on the image, or read the spot height printed next to pond P: Qwen2.5-VL-3B-Instruct 69%; SmolVLM2-2.2B-Instruct 69%; Qwen2-VL-2B-Instruct 94%; SmolVLM-256M-Instruct 0%. A model that reads labels but fails the water questions is failing the reasoning, not the eyesight.
- **Skill profile of the best model (Qwen2.5-VL-3B-Instruct):** clearly above chance on Measure along flow, Read elevation, Thermal threshold; **0% on Trace downstream, Flow direction**.
- **The dataset can teach the skill, a little.** Fine-tuning the smallest model on 300 ThirstMap tasks raised it from 10% to 19% on held-out scenes (p = 0.0026), and the tuned model now does better with the image than without it (19% vs 11%, p = 0.0033).

![accuracy by skill vs chance](results/open_models/chart_accuracy_by_skill.png)

Full tables, fine-tuning and caveats: [docs/FINDINGS.md](docs/FINDINGS.md) · per-run report: [results/open_models/REPORT.md](results/open_models/REPORT.md)
<!-- FINDINGS:END -->

## See it

**Demo:** [`docs/demo/index.html`](docs/demo/index.html) opens with the results, then walks one real scene through every pipeline step, then shows 64 tasks with each open model's real reply, an automatic ✓/✗ and an answer-key reveal, plus before-and-after pairs. Download the folder and open the page in a browser (no server needed).

**How a task is made** (one real scene, `level4_seed48947`, from `pipeline_visuals.py`):

| 1 Terrain | 2 Water simulation | 3 Scene script + traps | 4 Answer key |
|---|---|---|---|
| ![terrain](docs/pipeline/1_terrain.png) | ![water](docs/pipeline/2_water.png) | ![scene](docs/pipeline/3_scene.png) | ![answer](docs/pipeline/4_answer.png) |
| Fractal terrain, 4 × 4 km, 25 m cells | Priority-flood + D8 routing draws the streams | DC-1, outfall O, villages, wetlands; V6 is the near-but-other-stream trap | Traced downhill from O: **V4, V7** |
| **5 Independent check** | **6 Rendered (satellite style)** | **7 Pixel evidence** | **8 Twin** |
| ![check](docs/pipeline/5_check.png) | ![satellite](docs/pipeline/6_satellite.jpg) | ![pixels](docs/pipeline/7_pixels.jpg) | ![twin](docs/pipeline/8_twin.jpg) |
| pysheds agrees on 99.73% of cells, same answer to 10/10 questions | Also rendered as topographic map and thermal | 137/137 path cells visible in the pixels | Outfall moved (0.64% of pixels): answer becomes **V4, V6** |

| One scene, three image styles, one answer key | Difficulty dial, level 1 → 5 |
|---|---|
| ![styles](docs/gifs/styles.gif) | ![difficulty](docs/gifs/difficulty.gif) |
| **Counterfactual twin: one small change, the answer must flip** | **Appearance variants: the answer must NOT change** |
| ![counterfactual](docs/gifs/counterfactual.gif) | ![appearance](docs/gifs/appearance.gif) |

![real terrain](docs/gifs/real_terrain.gif)

*Real terrain (Copernicus elevation + ESA land cover) for four Indian data-centre hubs; the facility and villages are hypothetical.*

## What it produces

For every scene, the **same answer key** is rendered as three image styles:

| 🛰️ Satellite-style | 🗺️ Topographic map | 🌡️ Thermal |
|---|---|---|
| Relief shading, land cover, channels, villages, data-centre roofs and cooling towers | Contours, streams, symbols | Water temperature above normal on a 0–15 °C colour scale |

…and up to **10 question types**. None of them is a counting task:

| Q | Visual skill | Example | Styles |
|---|---|---|---|
| Q1 | Trace downstream | Which villages receive DC-1's wastewater? | sat, map |
| Q2 | Order along a path | Which village receives it first? | sat, map |
| Q3 | Nature-based fix | Which wetland site cleans ALL the wastewater before ANY village? | sat, map |
| Q4 | Read elevation | Which farms lie lower than pond P (gravity reuse)? | map |
| Q5 | Flow direction | Which way does the stream flow below the outfall? | sat, map |
| Q6 | Siting | Which proposed site's wastewater reaches no village? | sat, map |
| Q7 | Trace upstream | Which villages share the water source at intake I? | sat, map |
| Q8 | Colour-scale threshold | At which monitoring points is water > 3 °C warmer? | thermal |
| Q9 | Colour-scale value | How many °C warmer is the water at M2? | thermal |
| Q10 | Measure along a winding path | How far (m) does the wastewater travel along the stream to the first village? | sat, map |

**Traps are built in:** a village on the *same* stream but *upstream*, a village *close* to the data centre but on *another* stream, a wetland placed *after* a village (too late), and monitoring points upstream or on other streams. When a model answers wrong, the scorer names the trap it fell for.

**Counterfactual twins:** for almost every scene (306 of 308), the dataset also contains a **twin with one minimal, visible change that must flip the answer**. The twin is otherwise identical: same terrain, villages and labels (≈0.5% of pixels change). The change rotates between three kinds:

| Twin kind | What changes in the image | Answers that flip |
|---|---|---|
| Outfall moved | The pipe is rerouted and O sits on a different stream | Q1, Q2 |
| Intake moved | Intake I moves to a nearby point, often across a confluence | Q7 |
| Thermal | The cooling water is hotter or cooler (colours only) | Q8, Q9 |

**Pair accuracy** counts a pair only if both versions are answered correctly. It exposes models that answer from habit instead of looking. For example, the offline `mock:stubborn` baseline (it never notices a change) scores **87% on single tasks but 0% pair accuracy**.

**Eye-exam difficulty dial (levels 1–5):** rougher terrain, more ridges, more distractor streams, more villages and a finer contour interval. The report shows each model's **breaking level** per skill.

**Real-terrain mode:** the same pipeline runs on real **Copernicus 30 m elevation + ESA WorldCover land cover** for four Indian data-centre hubs: **Navi Mumbai, Hyderabad, Pune (Hinjewadi) and Chennai (Ambattur)**. Facility placements there are hypothetical.

**Current dataset:** 308 scenes and **5,761 tasks** (4,642 synthetic, 1,119 on real terrain), including **740 counterfactual pairs**; 2.1 GB of images. Built in about 18 minutes on 4 CPU cores. The **full dataset** is published as a GitHub Release (three zip parts with SHA-256 checksums, plus its manifest, validation report and verification). The `dataset-release` workflow **rebuilds it from the code on GitHub's own runners** whenever a `dataset-v*` tag is pushed, using the locked versions in `requirements-lock.txt`. A ready-to-use slice ships in the repo as **[`dataset_sample/`](dataset_sample/)**: 28 scenes plus their twins, 529 tasks and 69 pairs, in the same format, so you can run `evaluate.py --dataset dataset_sample` straight away.

---

## How answers are established and validated (independently of any model)

1. **Water simulation:** priority-flood depression filling, then D8 steepest-descent routing, then flow accumulation. Every answer is computed from this.
2. **Every question must pass every relevant check, or it is dropped. Nothing is hand-edited:**

| Check | What it proves |
|---|---|
| **V1** independent recomputation | A third-party library (**pysheds**) re-derives flow directions and every answer. Disagreement means the question is dropped (≈99.9% cell agreement in practice). |
| **V2** known-answer tests | Tilted plane, V-valley, ridge split, bowl-to-lake (`tests/test_hydrology.py`) |
| **V3** counterfactual | Unit test: removing a ridge must change the answer. In the dataset: 740 linked twin pairs whose answers provably differ, each twin independently re-validated (V1–V11) |
| **V4** determinism | Same seed gives byte-identical images and answers |
| **V5/V7/V8** margins | No farm within 3 m of the pond's height, unaffected villages ≥ 5 cells from the path, exactly one correct wetland, no temperature within 0.8 °C of the threshold |
| **V9** pixel evidence | The answer path is checked **in the rendered pixels** of each style |
| **V10** legibility | Labels never overlap and stay inside the image |
| **V11** style applicability | Questions are only asked in styles that contain the evidence |
| **V13** blind baseline | Every question is also asked **without the image**; tasks guessable blind are flagged |
| **V14** answer balance | Correct-answer positions and set sizes are rotated across the dataset |

`dataset/manifest.json` records pass rates and every dropped question with its reason. **[`docs/VALIDATION_REPORT.md`](docs/VALIDATION_REPORT.md)** collects all of the evidence in one place: test results, every validator's pass rate, pysheds agreement (99.85% of cells on average, never below 99.35%), dropped questions, answer balance, counterfactual pairs and baselines. Regenerate it with `python3 validation_report.py`.

**Human baseline (V15):** `python3 human_eval.py build` writes `human_eval/index.html`, a page where a person answers 27 tasks spanning every skill (no answers shown). `python3 human_eval.py score answers_*.json` scores them with the same scorer the models get.

---

## Quick start

One command reproduces everything (tests, dataset, baselines, eye exam, reports, verification, demo):

```bash
./run_all.sh            # full benchmark, about 25 min on 4 cores
./run_all.sh --quick    # small version, about 2 min
```

Or run each stage yourself:

```bash
pip install -r requirements.txt
python3 -m pytest -q                                    # 41 tests
python3 generate.py --level 3 --seed 11 --twin          # one scene + its counterfactual twin -> out/
python3 generate.py --level 3 --seed 5 --real navi_mumbai
python3 build_dataset.py --per-level 18 --real-per-location 9 --out dataset --workers 4
python3 evaluate.py --dataset dataset --models mock:oracle mock:random mock:stubborn --blind --run offline_baselines
python3 pipeline_visuals.py --scene level4_seed48947 --out docs/pipeline
python3 build_demo.py --dataset dataset --run results/open_models --baselines results/offline_baselines --pipeline docs/pipeline --out docs/demo
```

**Free open models, no keys (CPU or GPU):**

```bash
./run_open_models.sh                                           # 4 open models -> results/open_models/
MODELS="Qwen/Qwen2.5-VL-3B-Instruct" ./run_open_models.sh      # just one
python3 evaluate.py --dataset dataset --models hf:Qwen/Qwen2.5-VL-3B-Instruct --variants 24 --run open_models
python3 finetune.py --test-run results/open_models --train-per-q 30 --epochs 2   # can the data teach the skill?
python3 findings.py --run results/open_models                  # docs/FINDINGS.md + README findings, from the numbers
```

`hf:MODEL_ID[@NNNpx]` runs any Hugging Face image-text-to-text model through `transformers`. Probes (`--probes`) check whether a model can read the labels and colour scale at all, before blaming its reasoning. Variants (`--variants`) ask the same question about the same scene in dry season, monsoon, haze and coarse-sensor looks: the answer must not change.

Evaluating real models (keys are read from the environment, **never stored in code**):

```bash
export ANTHROPIC_API_KEY=...        # or: ant auth login
python3 evaluate.py --dataset dataset --per-cell 3 --blind --run frontier \
    --models claude:claude-opus-5-5 claude:claude-sonnet-5-5 openai:MODEL@BASE_URL gemini:MODEL
```

`--per-cell N` samples N tasks per (question × style × level) cell, so a run covers everything at a predictable cost. Runs resume after interruption. Token usage and cost are recorded per call.

**Adaptive eye exam (cheapest way to find breaking points):**

```bash
python3 staircase.py --dataset dataset --models claude:claude-opus-5-5 --trials 16 --run opus_eye
```

This uses a 2-down/1-up staircase (Levitt 1971): two correct answers in a row make the next task harder, one wrong answer makes it easier. It converges where the model is right about 71% of the time, so lucky guesses can't climb. That's about 144 calls per model instead of about 2,000. Offline check: the oracle scores 5.5 (never fails) on every skill and the random guesser 0.5–1.5.

## Results status (read this first)
- **Open models, real runs:** four free open-weight models from Hugging Face (Qwen2.5-VL-3B, Qwen2-VL-2B, SmolVLM2-2.2B, SmolVLM-256M) were run locally on CPU on the same tasks. Their numbers are in **Findings** above, in [`docs/FINDINGS.md`](docs/FINDINGS.md) and in [`results/open_models/REPORT.md`](results/open_models/REPORT.md). Every raw answer is in `results/open_models/responses.jsonl`.
- **Frontier API models** (Claude, GPT, Gemini) have not been run yet; that needs API keys. The harness is the same: one command, below.
- **Offline baselines** (`mock:oracle`, `mock:random`, `mock:stubborn`) test the dataset and the scorer. They are **not model findings**.
- **[`docs/VERIFICATION.md`](docs/VERIFICATION.md)** (from `verify_results.py`, which shares no code with the report) shows:
  - every reported number recomputed independently from the raw responses (exact match);
  - the random baseline at its exact mathematical chance level (13.8% expected vs 13.7% observed, over 5,761 tasks);
  - 10 sampled dataset scenes regenerated **byte-for-byte** from the code and their seeds (10/10);
  - spot-check sheets of random tasks (image, answer key and reveal) for checking by eye.
- **Exact inputs:** [`eval_set/`](eval_set/) holds exactly the 256 tasks and 330 MB of images the open models saw (168 questions, 16 reading checks, 72 appearance variants), with SHA-256 checksums and answer reveals. Repeat the run on identical images with `python3 evaluate.py --dataset eval_set --all --models hf:MODEL_ID --run rerun`.

## Outputs of an evaluation run (`results/<run>/`)
- `REPORT.md`: overall accuracy (with vs. without image), accuracy by skill, **breaking level per skill**, **map vs satellite** consistency, **counterfactual pair accuracy** and "unchanged answer" rate, trap fall rate and error diagnosis, cost
- `chart_accuracy_by_skill.png`, `chart_eye_exam.png`, `chart_by_style.png`
- `summary.json`, `responses.jsonl` (raw answers, parsed answers, scores, error tags, tokens)

## Architecture

```
thirstmap/terrain.py      fractal terrain, priority-flood, D8 routing, accumulation, tracing
thirstmap/scene.py        scene script: data centre, outfall, villages (+traps), wetlands, sites, intake, heat plume
thirstmap/realterrain.py  real Copernicus DEM + ESA WorldCover windows for Indian locations
thirstmap/questions.py    10 question types -> answer key (options, traps, styles)
thirstmap/render_sat.py   satellite-style renderer
thirstmap/render_map.py   topographic map renderer
thirstmap/render_thermal.py thermal false-colour renderer
thirstmap/validate.py     V1–V11 validators (pysheds cross-check, margins, pixel evidence, labels)
thirstmap/counterfactual.py twins: one minimal change (outfall / intake / temperature) that must flip the answer
thirstmap/dataset.py      tasks (question x style) with prompts and scoring rules
thirstmap/models.py       Claude / OpenAI-compatible / Gemini / Hugging Face adapters + offline oracle, random & stubborn baselines
thirstmap/scoring.py      robust answer parsing, scoring (exact / set-F1 / tolerance), error diagnosis
generate.py               scene -> render -> validate -> keep / drop / regenerate
build_dataset.py          parallel batch build + manifest (counts, validation pass rates, answer balance)
evaluate.py, report.py    model runs, metrics, charts, markdown report
build_demo.py             self-contained demo page: results, pipeline walkthrough, tasks with real replies -> ✓/✗ -> answer reveal
pipeline_visuals.py       one scene through every pipeline step (terrain, water, scene, answer, checks, styles, twin)
staircase.py              adaptive eye exam (2-down/1-up) per model x skill
human_eval.py             human baseline page + scorer (same tasks, same scorer)
validation_report.py      collects all validation evidence into docs/VALIDATION_REPORT.md
probes.py                 perception probes: can the model read labels, heights and the colour scale at all?
variants.py               appearance variants (monsoon / haze / coarse sensor) that must not change the answer
run_open_models.sh        four free Hugging Face models, same tasks, no keys
finetune.py               LoRA fine-tune of a small open model on held-out scenes; base vs tuned
findings.py               writes docs/FINDINGS.md and the README findings from summary.json
publish_eval_set.py       copies exactly the evaluated tasks + images to eval_set/ with checksums
verify_results.py         independent recomputation, chance check, byte-for-byte regeneration
make_gifs.py              the GIFs in this README
```

## Honest limitations
- Synthetic terrain is simplified; D8 routing ignores groundwater, canals, pipes and seasonality.
- The heat plume is a simple decay-and-mixing model, not a hydrodynamic simulation.
- Copernicus DEM is a surface model (includes trees and buildings); we smooth it lightly. Urban flow paths are approximate.
- Real-terrain scenes use hypothetical facilities and villages; we make no claims about real facilities.
- Some impact statistics come from secondary reporting and are estimates (see the brief for sources).
- The OpenAI-compatible and Gemini adapters follow the official SDKs but were not exercised in the build environment (no keys there).
- Reproducibility is byte-for-byte on the same platform. A different machine can build a slightly different (equally valid) dataset because of floating-point and font-rendering details: GitHub's runners built 310 scenes / 5,779 tasks where our machine built 308 / 5,761. That is why the exact evaluated inputs are published in `eval_set/`.
- The open models were small (0.26B–3B parameters) and ran on CPU with greedy decoding; larger models may do much better. The fine-tuning test used images reduced to 512 px.

## Data credits
Copernicus DEM GLO-30 (© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA; all rights reserved), modified · ESA WorldCover 10 m 2021 v200 (CC BY 4.0).
