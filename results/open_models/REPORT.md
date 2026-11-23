# ThirstMap evaluation report

## Overall

| Model | With image | Without image (blind) | Tasks |
|---|---|---|---|
| hf:HuggingFaceTB/SmolVLM-256M-Instruct | 8% | 10% | 144 |
| hf:Qwen/Qwen2-VL-2B-Instruct | 8% | 9% | 144 |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 16% | 13% | 144 |

## Better than guessing?

Chance = expected accuracy of a random guesser on exactly these tasks (from each task's options). p = one-sided binomial test that the model beats chance.

| Model | Correct | Accuracy | Chance | p-value |
|---|---|---|---|---|
| hf:HuggingFaceTB/SmolVLM-256M-Instruct | 11/144 | 8% | 13% | 0.99 |
| hf:Qwen/Qwen2-VL-2B-Instruct | 12/144 | 8% | 13% | 0.97 |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 23/144 | 16% | 13% | 0.18 |

## Accuracy by visual skill

Tasks = distinct tasks per skill (every model answers the same ones); with 10-30 tasks per skill, differences of a few points are within noise.

| Skill | Tasks | Chance | hf:HuggingFaceTB/SmolVLM-256M-Instruct | hf:Qwen/Qwen2-VL-2B-Instruct | hf:Qwen/Qwen2.5-VL-3B-Instruct |
|---|---|---|---|---|---|
| Trace downstream | 15 | 2% | 13% | 0% | 0% |
| Order along flow | 24 | 18% | 0% | 17% | 17% |
| Measure along flow | 10 | 11% | 0% | 20% | 30% |
| Place wetland | 10 | 25% | 10% | 40% | 30% |
| Site selection | 10 | 33% | 0% | 0% | 30% |
| Trace upstream | 30 | 4% | 0% | 0% | 10% |
| Flow direction | 10 | 12% | 20% | 10% | 0% |
| Read elevation | 5 | 8% | 20% | 20% | 20% |
| Thermal threshold | 19 | 11% | 16% | 0% | 26% |
| Thermal value | 11 | 20% | 18% | 0% | 9% |

## Eye exam: breaking level (first difficulty where accuracy < 50%)

| Skill | hf:HuggingFaceTB/SmolVLM-256M-Instruct | hf:Qwen/Qwen2-VL-2B-Instruct | hf:Qwen/Qwen2.5-VL-3B-Instruct |
|---|---|---|---|
| Trace downstream | 3 | 1 | 1 |
| Order along flow | 1 | 2 | 2 |
| Measure along flow | 1 | 1 | 1 |
| Place wetland | 1 | 5 | 1 |
| Site selection | 1 | 1 | 1 |
| Trace upstream | 1 | 1 | 1 |
| Flow direction | 1 | 1 | 1 |
| Read elevation | 2 | 2 | 2 |
| Thermal threshold | 1 | 1 | 1 |
| Thermal value | 1 | 1 | 1 |

## Map vs satellite (same scene, same question)

| Model | Pairs | Both right | Only map right | Only satellite right | Both wrong |
|---|---|---|---|---|---|

## Counterfactual pairs (one minimal change that must flip the answer)

Pair accuracy counts a pair only if BOTH the original and its twin are answered correctly. 'Unchanged answer' = the model gave the same answer to both, although the correct answer changed.

| Model | Pairs | Single-task accuracy | Pair accuracy | Unchanged answer |
|---|---|---|---|---|
| hf:HuggingFaceTB/SmolVLM-256M-Instruct | 30 | 5% | 0% | 73% |
| hf:Qwen/Qwen2-VL-2B-Instruct | 30 | 5% | 0% | 87% |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 30 | 18% | 0% | 87% |

## Perception probes: can the model even read the image?

No reasoning needed: these only ask the model to read what is printed on the image. Low scores here mean failures elsewhere start with perception, not reasoning.

| Probe | hf:HuggingFaceTB/SmolVLM-256M-Instruct | hf:Qwen/Qwen2-VL-2B-Instruct | hf:Qwen/Qwen2.5-VL-3B-Instruct |
|---|---|---|---|
| Read village labels (map) | 0% (n=4) | 100% (n=4) | 50% (n=4) |
| Read village labels (satellite) | 0% (n=4) | 100% (n=4) | 25% (n=4) |
| Read pond spot height (map) | 0% (n=4) | 100% (n=4) | 100% (n=4) |
| Read monitoring labels (thermal) | 0% (n=4) | 75% (n=4) | 100% (n=4) |

## Traps and error diagnosis

| Model | Trap tasks | Fell for a trap | Most common errors |
|---|---|---|---|
| hf:HuggingFaceTB/SmolVLM-256M-Instruct | 98 | 18% | missed_some (56), unparseable_or_no_answer (36), extra_unrelated (11), underestimate (9) |
| hf:Qwen/Qwen2-VL-2B-Instruct | 98 | 66% | trap:downstream_not_upstream (29), trap:other_stream (18), missed_some (16), unparseable_or_no_answer (15) |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 98 | 27% | missed_some (52), extra_unrelated (21), wrong_choice (19), overestimate (13) |

Tasks a majority of real models answered correctly WITHOUT the image: 12

## Cost

| Model | Input tokens | Output tokens | USD | Mean latency (s) |
|---|---|---|---|---|
| hf:HuggingFaceTB/SmolVLM-256M-Instruct | 199768 | 8185 | 0 | 9.73 |
| hf:Qwen/Qwen2-VL-2B-Instruct | 168420 | 5055 | 0 | 6.05 |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 168420 | 2857 | 0 | 6.69 |

![skills](chart_accuracy_by_skill.png)

![eye exam](chart_eye_exam.png)

![styles](chart_by_style.png)
