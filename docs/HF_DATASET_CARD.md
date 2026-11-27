---
license: cc-by-4.0
pretty_name: ThirstMap
task_categories:
  - visual-question-answering
language:
  - en
tags:
  - benchmark
  - synthetic
  - geospatial
  - hydrology
  - counterfactual
  - multimodal-evaluation
size_categories:
  - 1K<n<10K
---

# ThirstMap: can AI trace water through the landscape?

A visual reasoning benchmark generated from code. Each scene is a landscape whose water flow is simulated
(priority-flood + D8 routing), so every reference answer is computed, not labelled, and is re-derived by an
independent hydrology library (pysheds) before release. Scenes show an AI data centre, its wastewater outfall,
villages, candidate wetlands and siting options; questions ask where the water goes.

- **5,761 tasks** (5,330 after the audit's exclusions) from 308 scenes (4,642 synthetic, 1,119 on real terrain for Navi Mumbai, Hyderabad, Pune and
  Chennai from Copernicus DEM GLO-30 and ESA WorldCover)
- **3 image styles** per scene: satellite-style, topographic map, thermal; **5 difficulty levels**
- **10 skills, no counting**: trace downstream, order along the flow, distance along a winding stream, wetland
  placement, siting, elevation reading, flow direction, upstream catchment, colour-scale threshold and value
- **740 counterfactual pairs**: a twin with one minimal change (outfall, intake or water temperature) that must
  flip the answer; pair accuracy exposes answering from habit
- **Appearance variants** (monsoon, haze, coarse sensor) whose answers must not change; **reading checks**

## Files

`tasks.jsonl` (one task per line: `task_id`, `image`, `reveal`, `question`, `prompt`, `answer`, `options`,
`scoring`, `traps`, `skill`, `style`, `level`, `pair_id`, …), `scenes/<scene>/` (images, answer reveals,
`answer_key.json`, `validation.json`), `probes.jsonl`, `variants.jsonl`, `manifest.json`, and `errata.jsonl`:
tasks excluded by the dataset audit (labels under the scale bar, north arrow or legend, and 6 scenes with more items than designed; see
`docs/AUDIT.md` in the repository). Leave errata tasks out of any score.

```python
import json
tasks = [json.loads(l) for l in open("tasks.jsonl")]
bad = {json.loads(l)["task_id"] for l in open("errata.jsonl")}
tasks = [t for t in tasks if t["task_id"] not in bad]
```

Score replies with the repository's scorer (`thirstmap/scoring.py`): set-F1 or exact for label answers, a
tolerance for numbers, compass sectors for directions; wrong answers are tagged with the trap they fell for.

## Two newer task sets (in the repository's `eval_set/`)

- `eval_set/trace/`: 22 images with the simulated route of the wastewater as a list of grid cells, the renderer's
  cell-to-pixel mapping, the stream network and the cells upstream of the outfall. Models draw the route as points;
  `thirstmap/paths.py` scores the line cell by cell (5 before-and-after pairs where only the outfall moved).
- `eval_set/cloud/`: 20 scenes, each as a clear image (the published one), a version with a cloud over the stretch
  that decides the answer (correct answer: "cannot be determined") and the same cloud elsewhere (a decoy). `items.json`
  holds, per item, the proof that a second hidden landscape fits every visible pixel and gives other villages, and the
  pixel checks. Answer keys are included so every item rebuilds from its seed.

## Results so far

See `docs/FINDINGS.md` and `LEADERBOARD.md` in the repository. In short: open models up to 3B parameters score
at chance level; Gemini Flash-Lite models score about three times chance on the same questions (and fall to chance
without the image); Gemini 3.5 Flash scores 77%, yet gets both halves of only 6 of 19 before-and-after pairs right.

## Licence and credits

CC BY 4.0. Real-terrain scenes use Copernicus DEM GLO-30 (© DLR e.V. 2010-2014 and © Airbus Defence and Space
GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA) and ESA WorldCover 2021 v200 (CC BY 4.0).
All facilities, villages and temperatures are hypothetical.

Code and full pipeline: https://github.com/yugesh1111/THIRSTMAP · Citation: see `CITATION.cff` (Amritha S, 2026).
