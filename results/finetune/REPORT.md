# ThirstMap evaluation report

## Overall

| Model | With image | Without image (blind) | Tasks |
|---|---|---|---|
| hf:SmolVLM-256M-Instruct@512px (base) | 10% | 10% | 168 |
| hf:SmolVLM-256M-Instruct@512px (fine-tuned on ThirstMap) | 19% | 11% | 168 |

## Better than guessing?

Chance = expected accuracy of a random guesser on exactly these tasks (from each task's options). p = one-sided binomial test that the model beats chance.

| Model | Correct | Accuracy | Chance | p-value |
|---|---|---|---|---|
| hf:SmolVLM-256M-Instruct@512px (base) | 16/168 | 10% | 13% | 0.94 |
| hf:SmolVLM-256M-Instruct@512px (fine-tuned on ThirstMap) | 32/168 | 19% | 13% | 0.021 |

### Strict check: well-formed replies only

The scorer is lenient: it accepts a correct answer even when the reply is badly formatted. Counting a reply as right only if it is also well-formed (JSON with "answer", or a plain JSON value):

| Model | Well-formed replies | Accuracy (all) | Accuracy (well-formed only) |
|---|---|---|---|
| hf:SmolVLM-256M-Instruct@512px (base) | 1% | 10% | 0% |
| hf:SmolVLM-256M-Instruct@512px (fine-tuned on ThirstMap) | 99% | 19% | 19% |

## Accuracy by visual skill

Tasks = distinct tasks per skill (every model answers the same ones); with 10-30 tasks per skill, differences of a few points are within noise.

| Skill | Tasks | Chance | hf:SmolVLM-256M-Instruct@512px (base) | hf:SmolVLM-256M-Instruct@512px (fine-tuned on ThirstMap) |
|---|---|---|---|---|
| Trace downstream | 19 | 2% | 0% | 0% |
| Order along flow | 28 | 18% | 0% | 25% |
| Measure along flow | 14 | 10% | 7% | 29% |
| Place wetland | 13 | 25% | 23% | 38% |
| Site selection | 13 | 33% | 0% | 15% |
| Trace upstream | 33 | 4% | 9% | 9% |
| Flow direction | 13 | 12% | 0% | 15% |
| Read elevation | 5 | 8% | 20% | 0% |
| Thermal threshold | 19 | 11% | 32% | 37% |
| Thermal value | 11 | 20% | 18% | 18% |

## Eye exam: breaking level (first difficulty where accuracy < 50%)

| Skill | hf:SmolVLM-256M-Instruct@512px (base) | hf:SmolVLM-256M-Instruct@512px (fine-tuned on ThirstMap) |
|---|---|---|
| Trace downstream | 1 | 1 |
| Order along flow | 1 | 1 |
| Measure along flow | 1 | 1 |
| Place wetland | 1 | 1 |
| Site selection | 1 | 1 |
| Trace upstream | 1 | 1 |
| Flow direction | 1 | 1 |
| Read elevation | 2 | 1 |
| Thermal threshold | 1 | 1 |
| Thermal value | 1 | 1 |

## Map vs satellite (same scene, same question)

| Model | Pairs | Both right | Only map right | Only satellite right | Both wrong |
|---|---|---|---|---|---|

## Counterfactual pairs (one minimal change that must flip the answer)

Pair accuracy counts a pair only if BOTH the original and its twin are answered correctly. 'Unchanged answer' = the model gave the same answer to both, although the correct answer changed.

| Model | Pairs | Single-task accuracy | Pair accuracy | Unchanged answer |
|---|---|---|---|---|
| hf:SmolVLM-256M-Instruct@512px (base) | 30 | 18% | 0% | 77% |
| hf:SmolVLM-256M-Instruct@512px (fine-tuned on ThirstMap) | 30 | 22% | 0% | 93% |

## Traps and error diagnosis

| Model | Trap tasks | Fell for a trap | Most common errors |
|---|---|---|---|
| hf:SmolVLM-256M-Instruct@512px (base) | 112 | 20% | missed_some (62), unparseable_or_no_answer (52), extra_unrelated (22), underestimate (14) |
| hf:SmolVLM-256M-Instruct@512px (fine-tuned on ThirstMap) | 112 | 35% | missed_some (54), extra_unrelated (27), wrong_choice (26), trap:downstream_not_upstream (19) |

Tasks a majority of real models answered correctly WITHOUT the image: 0

## Cost

| Model | Input tokens | Output tokens | USD | Mean latency (s) |
|---|---|---|---|---|
| hf:SmolVLM-256M-Instruct@512px (base) | 0 | 0 | 0 | 1.98 |
| hf:SmolVLM-256M-Instruct@512px (fine-tuned on ThirstMap) | 0 | 0 | 0 | 0.95 |

![skills](chart_accuracy_by_skill.png)

![eye exam](chart_eye_exam.png)

![styles](chart_by_style.png)
