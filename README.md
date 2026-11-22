# ThirstMap — can AI trace water through the landscape?

*Innodata AI Hackathon 2026 · Track 2: Visual Task Factory*

> **AI is drinking India's water. We test whether AI can even see where that water goes.**

India's data centres use an estimated ~150 billion litres of water a year, and that could reach ~358 billion by 2030. About 70% of capacity sits in water-stressed Mumbai and Chennai, and none of India's state data-centre policies require water-impact mapping. AI geospatial agents are being built to answer exactly these questions from imagery: *Where does this facility's warm wastewater go? Which villages receive it? Where could a wetland clean it?*

**ThirstMap is a factory of visual tasks** that tests whether frontier multimodal models can be trusted with that job. Our code builds each landscape and simulates its water, so **it already knows every answer**, much like the brief's bar-chart example but for terrain and water flow.

See [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) for the full problem statement, sources, and a line-by-line fit to the Track 2 brief.

---

## What it produces

For every scene, the **same answer key** is rendered as three image styles:

| 🛰️ Satellite-style | 🗺️ Topographic map | 🌡️ Thermal |
|---|---|---|
| Relief shading, land cover, channels, villages, data-centre roofs and cooling towers | Contours, streams, symbols | Water temperature above normal on a 0–15 °C colour scale |

…and up to **9 question types**. None of them is a counting task:

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

**Traps are built in:** a village on the *same* stream but *upstream*, a village *close* to the data centre but on *another* stream, a wetland placed *after* a village (too late), and monitoring points upstream or on other streams. When a model answers wrong, the scorer names the trap it fell for.

**Eye-exam difficulty dial (levels 1–5):** rougher terrain, more ridges, more distractor streams, more villages and a finer contour interval. The report shows each model's **breaking level** per skill.

**Real-terrain mode:** the same pipeline runs on real **Copernicus 30 m elevation + ESA WorldCover land cover** for Navi Mumbai and Hyderabad, both Indian data-centre hubs. Facility placements there are hypothetical.

---

## How answers are established and validated (independently of any model)

1. **Water simulation:** priority-flood depression filling, then D8 steepest-descent routing, then flow accumulation. Every answer is computed from this.
2. **Every question must pass every relevant check, or it is dropped. Nothing is hand-edited:**

| Check | What it proves |
|---|---|
| **V1** independent recomputation | A third-party library (**pysheds**) re-derives flow directions and every answer. Disagreement means the question is dropped (≈99.9% cell agreement in practice). |
| **V2** known-answer tests | Tilted plane, V-valley, ridge split, bowl-to-lake (`tests/test_hydrology.py`) |
| **V3** counterfactual | Removing a ridge must change the answer |
| **V4** determinism | Same seed gives byte-identical images and answers |
| **V5/V7/V8** margins | No farm within 3 m of the pond's height, unaffected villages ≥ 5 cells from the path, exactly one correct wetland, no temperature within 0.8 °C of the threshold |
| **V9** pixel evidence | The answer path is checked **in the rendered pixels** of each style |
| **V10** legibility | Labels never overlap and stay inside the image |
| **V11** style applicability | Questions are only asked in styles that contain the evidence |
| **V13** blind baseline | Every question is also asked **without the image**; tasks guessable blind are flagged |
| **V14** answer balance | Correct-answer positions and set sizes are rotated across the dataset |

`dataset/manifest.json` records pass rates and every dropped question with its reason.

---

## Quick start

```bash
pip install -r requirements.txt
python3 -m pytest -q                                    # 22 tests
python3 generate.py --level 3 --seed 11                 # one scene -> out/ (+ validation printout)
python3 generate.py --level 3 --seed 5 --real navi_mumbai
python3 build_dataset.py --per-level 18 --real-per-location 9 --out dataset --workers 4
python3 evaluate.py --dataset dataset --models mock:oracle mock:random --blind --run offline_baselines
python3 build_demo.py --dataset dataset --run results/offline_baselines --out demo   # open demo/index.html
```

Evaluating real models (keys are read from the environment, **never stored in code**):

```bash
export ANTHROPIC_API_KEY=...        # or: ant auth login
python3 evaluate.py --dataset dataset --per-cell 3 --blind --run frontier \
    --models claude:claude-opus-5-5 claude:claude-sonnet-5-5 openai:MODEL@BASE_URL gemini:MODEL
```

`--per-cell N` samples N tasks per (question × style × level) cell, so a run covers everything at a predictable cost. Runs resume after interruption. Token usage and cost are recorded per call.

## Outputs of an evaluation run (`results/<run>/`)
- `REPORT.md`: overall accuracy (with vs. without image), accuracy by skill, **breaking level per skill**, **map vs satellite** consistency, trap fall rate and error diagnosis, cost
- `chart_accuracy_by_skill.png`, `chart_eye_exam.png`, `chart_by_style.png`
- `summary.json`, `responses.jsonl` (raw answers, parsed answers, scores, error tags, tokens)

## Architecture

```
thirstmap/terrain.py      fractal terrain, priority-flood, D8 routing, accumulation, tracing
thirstmap/scene.py        scene script: data centre, outfall, villages (+traps), wetlands, sites, intake, heat plume
thirstmap/realterrain.py  real Copernicus DEM + ESA WorldCover windows for Indian locations
thirstmap/questions.py    9 question types -> answer key (options, traps, styles)
thirstmap/render_sat.py   satellite-style renderer
thirstmap/render_map.py   topographic map renderer
thirstmap/render_thermal.py thermal false-colour renderer
thirstmap/validate.py     V1–V11 validators (pysheds cross-check, margins, pixel evidence, labels)
thirstmap/dataset.py      tasks (question x style) with prompts and scoring rules
thirstmap/models.py       Claude / OpenAI-compatible / Gemini adapters + offline oracle & random baselines
thirstmap/scoring.py      robust answer parsing, scoring (exact / set-F1 / tolerance), error diagnosis
generate.py               scene -> render -> validate -> keep / drop / regenerate
build_dataset.py          parallel batch build + manifest (counts, validation pass rates, answer balance)
evaluate.py, report.py    model runs, metrics, charts, markdown report
build_demo.py             self-contained demo page: image -> question -> model answers -> ✓/✗ -> answer reveal
```

## Honest limitations
- Synthetic terrain is simplified; D8 routing ignores groundwater, canals, pipes and seasonality.
- The heat plume is a simple decay-and-mixing model, not a hydrodynamic simulation.
- Copernicus DEM is a surface model (includes trees and buildings); we smooth it lightly. Urban flow paths are approximate.
- Real-terrain scenes use hypothetical facilities and villages; we make no claims about real facilities.
- Some impact statistics come from secondary reporting and are estimates (see the brief for sources).
- The OpenAI-compatible and Gemini adapters follow the official SDKs but were not exercised in the build environment (no keys there).

## Data credits
Copernicus DEM GLO-30 (© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA; all rights reserved), modified · ESA WorldCover 10 m 2021 v200 (CC BY 4.0).
