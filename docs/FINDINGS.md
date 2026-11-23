# Findings: how well do vision-language models trace water through the landscape?

Four free, open-weight models from Hugging Face run locally on CPU. Every model answered the **same tasks**: one per (question × image style × difficulty) cell, 30 counterfactual pairs, perception probes, and every question again **without the image**. Claude and GPT run with the same harness once keys are available.

| Model | Size | Accuracy | Without image | Chance | p (beats chance) | Pair accuracy | Same answer to original & twin | Same answer in 4 looks | Reading checks |
|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-VL-3B-Instruct | 3B | **17%** (22/130) | 14% | 13% | 0.15 | 0% | 92% | 75% (n=20) | 69% (n=16) |
| Qwen2-VL-2B-Instruct | 2B | **9%** (12/130) | 9% | 13% | 0.95 | 0% | 85% | 95% (n=20) | 94% (n=16) |
| SmolVLM-256M-Instruct | 0.26B | **8%** (11/130) | 10% | 13% | 0.97 | 0% | 73% | – | 0% (n=16) |
| SmolVLM2-2.2B-Instruct | 2.2B | **8%** (11/130) | 12% | 13% | 0.97 | 0% | 81% | – | 69% (n=16) |

## Frontier check (Gemini, free API tier)

A free Gemini key allows 20 requests per model per day, so the frontier check uses request economy: **batched** = every question about one image in one request (18 images, 6 of them before-and-after pairs; images resized to 768 px), sent identically to Gemini and to the open models; **single** = one question per request, the protocol of the main table, on the 20 questions Gemini 3.5 Flash answered before its daily quota ran out.

| Model | Protocol | Questions | Accuracy | Chance | p (beats chance) | Both halves of a pair right | Same answer to original & twin | Tokens per answer |
|---|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | batched | 83 | **48%** (40/83) | 14% | 1.2e-13 | 0% (7) | 14% | 299 |
| gemini-3.5-flash-lite | batched | 83 | **40%** (33/83) | 14% | 7.6e-09 | 0% (7) | 29% | 302 |
| Qwen2.5-VL-3B-Instruct | batched | 83 | **12%** (10/83) | 14% | 0.75 | 0% (7) | 43% | 229 |
| Qwen2-VL-2B-Instruct | batched | 83 | **5%** (4/83) | 14% | 1 | 0% (7) | 43% | 229 |
| gemini-3.5-flash | single | 19 | **79%** (15/19) | 8% | 1.2e-13 | – | – | – |
| Qwen2.5-VL-3B-Instruct | single | 19 | **16%** (3/19) | 8% | 0.2 | – | – | – |
| Qwen2-VL-2B-Instruct | single | 19 | **11%** (2/19) | 8% | 0.46 | – | – | – |
| SmolVLM-256M-Instruct | single | 19 | **11%** (2/19) | 8% | 0.46 | – | – | – |
| SmolVLM2-2.2B-Instruct | single | 19 | **5%** (1/19) | 8% | 0.8 | – | – | – |

## What the numbers say

- **No open model in the main table is significantly better than random guessing** (all p ≥ 0.05). The best, Qwen2.5-VL-3B-Instruct, scores 17% against a chance level of 13% (p = 0.15).
- **A frontier model does much better, but is not reliable yet.** On the same 83 questions (batched protocol), gemini-3.1-flash-lite got 48% right against 12% for the best open model, Qwen2.5-VL-3B-Instruct (chance 14%, p = 1.2e-13). One question per request, gemini-3.5-flash got 79% of 19 questions against 16% for Qwen2.5-VL-3B-Instruct.
- **No model passes the before-and-after test.** Each twin changes one thing so the correct answer flips; Qwen2-VL-2B-Instruct, Qwen2.5-VL-3B-Instruct, gemini-3.1-flash-lite, gemini-3.5-flash-lite got both halves of **0 of 7** pairs right: the frontier models often change their answer for the twin, but never get both the original scene and its changed twin right.
- **The image barely helps.** Accuracy with vs without the image: Qwen2.5-VL-3B-Instruct 17% vs 14%; Qwen2-VL-2B-Instruct 9% vs 9%; SmolVLM-256M-Instruct 8% vs 10%; SmolVLM2-2.2B-Instruct 8% vs 12%.
- **Counterfactual twins expose answering from habit.** Share of pairs where the model gave the same answer to the original and to its twin (whose correct answer is different): Qwen2.5-VL-3B-Instruct 92% (both right: 0%); Qwen2-VL-2B-Instruct 85% (both right: 0%); SmolVLM-256M-Instruct 73% (both right: 0%); SmolVLM2-2.2B-Instruct 81% (both right: 0%).
- **Appearance changes move answers.** Share of question groups answered identically in the dry-season, monsoon, haze and coarse-sensor versions of the same scene (the correct answer is identical in all four): Qwen2.5-VL-3B-Instruct 75%; Qwen2-VL-2B-Instruct 95%.
- **Can they read the image at all?** Reading checks need no reasoning: list every village or monitoring-point label written on the image, or read the spot height printed next to pond P: Qwen2.5-VL-3B-Instruct 69%; Qwen2-VL-2B-Instruct 94%; SmolVLM-256M-Instruct 0%; SmolVLM2-2.2B-Instruct 69%. A model that reads labels but fails the water questions is failing the reasoning, not the eyesight.
- **Skill profile of the best model (Qwen2.5-VL-3B-Instruct):** clearly above chance on Measure along flow, Read elevation, Thermal threshold; **0% on Trace downstream, Flow direction**.
- **The dataset can teach the skill, a little.** Fine-tuning the smallest model on 300 ThirstMap tasks raised it from 10% to 19% on held-out scenes (p = 0.0096), and the tuned model now does better with the image than without it (19% vs 11%, p = 0.013).

## Accuracy by skill (chance = random guessing on the same tasks)

| Skill | Tasks | Chance | Qwen2.5-VL-3B-Instruct | Qwen2-VL-2B-Instruct | SmolVLM-256M-Instruct | SmolVLM2-2.2B-Instruct |
|---|---|---|---|---|---|---|
| Trace downstream | 13 | 2% | 0% | 0% | 15% | 8% |
| Order along flow | 23 | 18% | 17% | 17% | 0% | 4% |
| Measure along flow | 10 | 11% | 30% | 20% | 0% | 0% |
| Place wetland | 10 | 25% | 30% | 40% | 10% | 40% |
| Site selection | 9 | 33% | 33% | 0% | 0% | 0% |
| Trace upstream | 25 | 5% | 12% | 0% | 0% | 4% |
| Flow direction | 9 | 12% | 0% | 11% | 22% | 0% |
| Read elevation | 5 | 8% | 20% | 20% | 20% | 20% |
| Thermal threshold | 15 | 11% | 27% | 0% | 20% | 7% |
| Thermal value | 11 | 20% | 9% | 0% | 18% | 18% |

## Can the dataset teach the skill? (fine-tuning)

HuggingFaceTB/SmolVLM-256M-Instruct was fine-tuned with LoRA on 300 tasks for 2 epochs on CPU (27 min), using only scenes that never appear in the test set (108 held-out scene families, 150 test questions). Both versions answer the same test questions with the same image settings, and again without the image:

| Model | Accuracy | Without image | Chance | p (beats chance) | Well-formed replies | Accuracy, well-formed only |
|---|---|---|---|---|---|---|
| base | **10%** (15/150) | 11% | 14% | 0.93 | 1% | 0% |
| fine-tuned on ThirstMap | **19%** (28/150) | 11% | 14% | 0.056 | 99% | 19% |

Fine-tuning raised accuracy by 9 percentage points (paired test on the same questions: 20 answers became right, 7 became wrong, p = 0.0096). **The tuned model learned to use the image:** it scores 7 percentage points higher with the image than without it (16 questions right only with the image, 5 only without; p = 0.013), while the base model scored the same either way. So the gain is not just the answer format or typical answers. It is still far from reliable: most answers remain wrong.

| Skill | Chance | base | fine-tuned |
|---|---|---|---|
| Trace downstream | 2% | 0% | 0% |
| Order along flow | 18% | 0% | 19% |
| Measure along flow | 10% | 7% | 29% |
| Place wetland | 25% | 23% | 38% |
| Site selection | 33% | 0% | 8% |
| Trace upstream | 5% | 11% | 11% |
| Flow direction | 12% | 0% | 18% |
| Read elevation | 8% | 20% | 0% |
| Thermal threshold | 11% | 33% | 40% |
| Thermal value | 20% | 18% | 18% |

The adapter is in `models/SmolVLM-256M-Instruct-thirstmap-lora/` (22 MB); load it with `peft.PeftModel.from_pretrained`.

## Strict check: well-formed replies only

The scorer is lenient: a reply that names the right labels counts even if it is badly formatted (small models often write broken JSON). Counting only well-formed replies does not change the conclusion:

| Model | Well-formed replies | Accuracy (all) | Accuracy (well-formed only) |
|---|---|---|---|
| Qwen2.5-VL-3B-Instruct | 100% | 17% | 17% |
| Qwen2-VL-2B-Instruct | 92% | 9% | 9% |
| SmolVLM-256M-Instruct | 27% | 8% | 2% |
| SmolVLM2-2.2B-Instruct | 90% | 8% | 8% |

## Why the models fail

Every wrong answer is drawn on the image the model saw (`overlays.py`, shown in the demo under *Where the models sent the water*) and turned into what it would mean on the ground, for example: “V4 receives the warm wastewater but would not be warned.”

- **Built-in traps catch them.** Share of answers that picked a trap option (a village close to the data centre but on another stream, a village upstream of the outfall, a wetland after a village, a monitoring point on another stream): gemini-3.1-flash-lite 16% (7/44); gemini-3.5-flash-lite 18% (8/44); Qwen2.5-VL-3B-Instruct 27% (12/44); Qwen2-VL-2B-Instruct 52% (23/44).
- **It is not simply distance.** We tested whether wrong villages are the ones nearest the outfall (answering by proximity instead of flow): 37 of 155 wrong picks were the nearest non-receiving village, against 38 expected by chance, so a simple proximity shortcut does not explain the errors.

**Audit.** 431 of 5761 dataset tasks (7.5%) are excluded from every number on this page after a self-audit found labels hidden under the scale bar or legend and six malformed scenes ([`AUDIT.md`](AUDIT.md)); the conclusions are unchanged.

## Caveats

- The open models are small (0.26B–3B parameters) and ran on CPU with greedy decoding.
- About 10–30 tasks per skill per model: per-skill differences of a few points are noise; the overall test against chance uses all tasks.
- Images are synthetic renders; the real-terrain subset uses real elevation and land cover with hypothetical facilities.
- Exact inputs are published in `eval_set/` so the run can be repeated on identical images.
