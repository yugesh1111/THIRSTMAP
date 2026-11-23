# Findings: how well do vision-language models trace water through the landscape?

Four free, open-weight models from Hugging Face run locally on CPU. Every model answered the **same tasks**: one per (question × image style × difficulty) cell, 30 counterfactual pairs, perception probes, and every question again **without the image**. Claude and GPT run with the same harness once keys are available.

| Model | Size | Accuracy | Without image | Chance | p (beats chance) | Pair accuracy | Same answer to original & twin | Same answer in 4 looks | Reading checks |
|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-VL-3B-Instruct | 3B | **16%** (23/144) | 13% | 13% | 0.18 | 0% | 87% | 75% (n=24) | 69% (n=16) |
| SmolVLM2-2.2B-Instruct | 2.2B | **8%** (12/144) | 12% | 13% | 0.97 | 0% | 77% | – | 69% (n=16) |
| Qwen2-VL-2B-Instruct | 2B | **8%** (12/144) | 9% | 13% | 0.97 | 0% | 87% | 88% (n=24) | 94% (n=16) |
| SmolVLM-256M-Instruct | 0.26B | **8%** (11/144) | 10% | 13% | 0.99 | 0% | 73% | – | 0% (n=16) |

## Frontier check (Gemini, free API tier)

A free Gemini key allows 20 requests per model per day, so the frontier check uses request economy: **batched** = every question about one image in one request (18 images, 6 of them before-and-after pairs; images resized to 768 px), sent identically to Gemini and to the open models; **single** = one question per request, the protocol of the main table, on the 20 questions Gemini 3.5 Flash answered before its daily quota ran out.

| Model | Protocol | Questions | Accuracy | Chance | p (beats chance) | Both halves of a pair right | Same answer to original & twin | Tokens per answer |
|---|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | batched | 89 | **46%** (41/89) | 14% | 1.4e-13 | 0% (9) | 33% | 299 |
| gemini-3.5-flash-lite | batched | 89 | **39%** (35/89) | 14% | 1.7e-09 | 0% (9) | 22% | 302 |
| Qwen2.5-VL-3B-Instruct | batched | 89 | **11%** (10/89) | 14% | 0.79 | 0% (9) | 44% | 229 |
| Qwen2-VL-2B-Instruct | batched | 89 | **6%** (5/89) | 14% | 1 | 0% (9) | 33% | 229 |
| gemini-3.5-flash | single | 20 | **75%** (15/20) | 8% | 2.5e-13 | – | – | – |
| Qwen2.5-VL-3B-Instruct | single | 20 | **15%** (3/20) | 8% | 0.2 | – | – | – |
| Qwen2-VL-2B-Instruct | single | 20 | **10%** (2/20) | 8% | 0.47 | – | – | – |
| SmolVLM-256M-Instruct | single | 20 | **10%** (2/20) | 8% | 0.47 | – | – | – |
| SmolVLM2-2.2B-Instruct | single | 20 | **5%** (1/20) | 8% | 0.8 | – | – | – |

## What the numbers say

- **No open model in the main table is significantly better than random guessing** (all p ≥ 0.05). The best, Qwen2.5-VL-3B-Instruct, scores 16% against a chance level of 13% (p = 0.18).
- **A frontier model does much better, but is not reliable yet.** On the same 89 questions (batched protocol), gemini-3.1-flash-lite got 46% right against 11% for the best open model, Qwen2.5-VL-3B-Instruct (chance 14%, p = 1.4e-13). One question per request, gemini-3.5-flash got 75% of 20 questions against 15% for Qwen2.5-VL-3B-Instruct.
- **No model passes the before-and-after test.** Each twin changes one thing so the correct answer flips; Qwen2-VL-2B-Instruct, Qwen2.5-VL-3B-Instruct, gemini-3.1-flash-lite, gemini-3.5-flash-lite got both halves of **0 of 9** pairs right: the frontier models often change their answer for the twin, but never get both the original scene and its changed twin right.
- **The image barely helps.** Accuracy with vs without the image: Qwen2.5-VL-3B-Instruct 16% vs 13%; SmolVLM2-2.2B-Instruct 8% vs 12%; Qwen2-VL-2B-Instruct 8% vs 9%; SmolVLM-256M-Instruct 8% vs 10%.
- **Counterfactual twins expose answering from habit.** Share of pairs where the model gave the same answer to the original and to its twin (whose correct answer is different): Qwen2.5-VL-3B-Instruct 87% (both right: 0%); SmolVLM2-2.2B-Instruct 77% (both right: 0%); Qwen2-VL-2B-Instruct 87% (both right: 0%); SmolVLM-256M-Instruct 73% (both right: 0%).
- **Appearance changes move answers.** Share of question groups answered identically in the dry-season, monsoon, haze and coarse-sensor versions of the same scene (the correct answer is identical in all four): Qwen2.5-VL-3B-Instruct 75%; Qwen2-VL-2B-Instruct 88%.
- **Can they read the image at all?** Reading checks need no reasoning: list every village or monitoring-point label written on the image, or read the spot height printed next to pond P: Qwen2.5-VL-3B-Instruct 69%; SmolVLM2-2.2B-Instruct 69%; Qwen2-VL-2B-Instruct 94%; SmolVLM-256M-Instruct 0%. A model that reads labels but fails the water questions is failing the reasoning, not the eyesight.
- **Skill profile of the best model (Qwen2.5-VL-3B-Instruct):** clearly above chance on Measure along flow, Read elevation, Thermal threshold; **0% on Trace downstream, Flow direction**.
- **The dataset can teach the skill, a little.** Fine-tuning the smallest model on 300 ThirstMap tasks raised it from 10% to 19% on held-out scenes (p = 0.0026), and the tuned model now does better with the image than without it (19% vs 11%, p = 0.0033).

## Accuracy by skill (chance = random guessing on the same tasks)

| Skill | Tasks | Chance | Qwen2.5-VL-3B-Instruct | SmolVLM2-2.2B-Instruct | Qwen2-VL-2B-Instruct | SmolVLM-256M-Instruct |
|---|---|---|---|---|---|---|
| Trace downstream | 15 | 2% | 0% | 7% | 0% | 13% |
| Order along flow | 24 | 18% | 17% | 4% | 17% | 0% |
| Measure along flow | 10 | 11% | 30% | 0% | 20% | 0% |
| Place wetland | 10 | 25% | 30% | 40% | 40% | 10% |
| Site selection | 10 | 33% | 30% | 0% | 0% | 0% |
| Trace upstream | 30 | 4% | 10% | 3% | 0% | 0% |
| Flow direction | 10 | 12% | 0% | 0% | 10% | 20% |
| Read elevation | 5 | 8% | 20% | 20% | 20% | 20% |
| Thermal threshold | 19 | 11% | 26% | 11% | 0% | 16% |
| Thermal value | 11 | 20% | 9% | 18% | 0% | 18% |

## Can the dataset teach the skill? (fine-tuning)

HuggingFaceTB/SmolVLM-256M-Instruct was fine-tuned with LoRA on 300 tasks for 2 epochs on CPU (27 min), using only scenes that never appear in the test set (108 held-out scene families, 168 test questions). Both versions answer the same test questions with the same image settings, and again without the image:

| Model | Accuracy | Without image | Chance | p (beats chance) | Well-formed replies | Accuracy, well-formed only |
|---|---|---|---|---|---|---|
| base | **10%** (16/168) | 10% | 13% | 0.94 | 1% | 0% |
| fine-tuned on ThirstMap | **19%** (32/168) | 11% | 13% | 0.021 | 99% | 19% |

Fine-tuning raised accuracy by 10 percentage points (paired test on the same questions: 23 answers became right, 7 became wrong, p = 0.0026). **The tuned model learned to use the image:** it scores 8 percentage points higher with the image than without it (19 questions right only with the image, 5 only without; p = 0.0033), while the base model scored the same either way. So the gain is not just the answer format or typical answers. It is still far from reliable: most answers remain wrong.

| Skill | Chance | base | fine-tuned |
|---|---|---|---|
| Trace downstream | 2% | 0% | 0% |
| Order along flow | 18% | 0% | 25% |
| Measure along flow | 10% | 7% | 29% |
| Place wetland | 25% | 23% | 38% |
| Site selection | 33% | 0% | 15% |
| Trace upstream | 4% | 9% | 9% |
| Flow direction | 12% | 0% | 15% |
| Read elevation | 8% | 20% | 0% |
| Thermal threshold | 11% | 32% | 37% |
| Thermal value | 20% | 18% | 18% |

The adapter is in `models/SmolVLM-256M-Instruct-thirstmap-lora/` (22 MB); load it with `peft.PeftModel.from_pretrained`.

## Strict check: well-formed replies only

The scorer is lenient: a reply that names the right labels counts even if it is badly formatted (small models often write broken JSON). Counting only well-formed replies does not change the conclusion:

| Model | Well-formed replies | Accuracy (all) | Accuracy (well-formed only) |
|---|---|---|---|
| Qwen2.5-VL-3B-Instruct | 100% | 16% | 16% |
| SmolVLM2-2.2B-Instruct | 88% | 8% | 8% |
| Qwen2-VL-2B-Instruct | 92% | 8% | 8% |
| SmolVLM-256M-Instruct | 29% | 8% | 2% |

## Caveats

- The open models are small (0.26B–3B parameters) and ran on CPU with greedy decoding.
- About 10–30 tasks per skill per model: per-skill differences of a few points are noise; the overall test against chance uses all tasks.
- Images are synthetic renders; the real-terrain subset uses real elevation and land cover with hypothetical facilities.
- Exact inputs are published in `eval_set/` so the run can be repeated on identical images.
