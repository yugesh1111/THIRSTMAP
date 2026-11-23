# Findings: how well do open vision-language models trace water through the landscape?

Free, open-weight models from Hugging Face, run locally on CPU (no API keys). Every model answered the **same tasks**: one per (question × image style × difficulty) cell, 30 counterfactual pairs, perception probes, and every question again **without the image**. Frontier API models (Claude, GPT, Gemini) run with the same harness once keys are available.

| Model | Size | Accuracy | Without image | Chance | p (beats chance) | Pair accuracy | Same answer to original & twin | Same answer in 4 looks | Reading checks |
|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-VL-3B-Instruct | 3B | **16%** (23/144) | 13% | 13% | 0.18 | 0% | 87% | – | 69% (n=16) |
| Qwen2-VL-2B-Instruct | 2B | **8%** (12/144) | 9% | 13% | 0.97 | 0% | 87% | – | 94% (n=16) |
| SmolVLM-256M-Instruct | 0.26B | **7%** (10/137) | – | 13% | 0.99 | 0% | 77% | – | – |

*Interim: evaluation still running for SmolVLM-256M-Instruct (137 of 144 tasks so far); numbers for it will change and more models may be added.*

## What the numbers say

- **No open model is significantly better than random guessing overall** (all p ≥ 0.05). The best, Qwen2.5-VL-3B-Instruct, scores 16% against a chance level of 13% (p = 0.18).
- **The image barely helps.** Accuracy with vs without the image: Qwen2.5-VL-3B-Instruct 16% vs 13%; Qwen2-VL-2B-Instruct 8% vs 9%.
- **Counterfactual twins expose answering from habit.** Share of pairs where the model gave the same answer to the original and to its twin (whose correct answer is different): Qwen2.5-VL-3B-Instruct 87% (both right: 0%); Qwen2-VL-2B-Instruct 87% (both right: 0%); SmolVLM-256M-Instruct 77% (both right: 0%).
- **Can they read the image at all?** Reading checks need no reasoning: list every village or monitoring-point label written on the image, or read the spot height printed next to pond P: Qwen2.5-VL-3B-Instruct 69%; Qwen2-VL-2B-Instruct 94%. A model that reads labels but fails the water questions is failing the reasoning, not the eyesight.
- **Skill profile of the best model (Qwen2.5-VL-3B-Instruct):** clearly above chance on Measure along flow, Read elevation, Thermal threshold; **0% on Trace downstream, Flow direction**.

## Accuracy by skill (chance = random guessing on the same tasks)

| Skill | Tasks | Chance | Qwen2.5-VL-3B-Instruct | Qwen2-VL-2B-Instruct | SmolVLM-256M-Instruct |
|---|---|---|---|---|---|
| Trace downstream | 15 | 2% | 0% | 0% | 13% |
| Order along flow | 24 | 18% | 17% | 17% | 0% |
| Measure along flow | 10 | 11% | 30% | 20% | 0% |
| Place wetland | 10 | 25% | 30% | 40% | 10% |
| Site selection | 10 | 33% | 30% | 0% | 0% |
| Trace upstream | 30 | 4% | 10% | 0% | 0% |
| Flow direction | 10 | 12% | 0% | 10% | 20% |
| Read elevation | 5 | 8% | 20% | 20% | 20% |
| Thermal threshold | 19 | 11% | 26% | 0% | 12% |
| Thermal value | 11 | 20% | 9% | 0% | 18% |

## Caveats

- These are small open models (0.26B–3B parameters) on CPU, not frontier systems.
- About 10–30 tasks per skill per model: per-skill differences of a few points are noise; the overall test against chance uses all tasks.
- Images are synthetic renders; the real-terrain subset uses real elevation and land cover with hypothetical facilities.
- Exact inputs are published in `eval_set/` so the run can be repeated on identical images.
