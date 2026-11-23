# ThirstMap evaluation report

## Overall

| Model | With image | Without image (blind) | Tasks |
|---|---|---|---|
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 16% | 13% | 144 |

## Better than guessing?

Chance = expected accuracy of a random guesser on exactly these tasks (from each task's options). p = one-sided binomial test that the model beats chance.

| Model | Correct | Accuracy | Chance | p-value |
|---|---|---|---|---|
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 23/144 | 16% | 13% | 0.18 |

## Accuracy by visual skill

Tasks = distinct tasks per skill (every model answers the same ones); with 10-30 tasks per skill, differences of a few points are within noise.

| Skill | Tasks | Chance | hf:Qwen/Qwen2.5-VL-3B-Instruct |
|---|---|---|---|
| Trace downstream | 15 | 2% | 0% |
| Order along flow | 24 | 18% | 17% |
| Measure along flow | 10 | 11% | 30% |
| Place wetland | 10 | 25% | 30% |
| Site selection | 10 | 33% | 30% |
| Trace upstream | 30 | 4% | 10% |
| Flow direction | 10 | 12% | 0% |
| Read elevation | 5 | 8% | 20% |
| Thermal threshold | 19 | 11% | 26% |
| Thermal value | 11 | 20% | 9% |

## Eye exam: breaking level (first difficulty where accuracy < 50%)

| Skill | hf:Qwen/Qwen2.5-VL-3B-Instruct |
|---|---|
| Trace downstream | 1 |
| Order along flow | 2 |
| Measure along flow | 1 |
| Place wetland | 1 |
| Site selection | 1 |
| Trace upstream | 1 |
| Flow direction | 1 |
| Read elevation | 2 |
| Thermal threshold | 1 |
| Thermal value | 1 |

## Map vs satellite (same scene, same question)

| Model | Pairs | Both right | Only map right | Only satellite right | Both wrong |
|---|---|---|---|---|---|

## Counterfactual pairs (one minimal change that must flip the answer)

Pair accuracy counts a pair only if BOTH the original and its twin are answered correctly. 'Unchanged answer' = the model gave the same answer to both, although the correct answer changed.

| Model | Pairs | Single-task accuracy | Pair accuracy | Unchanged answer |
|---|---|---|---|---|
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 30 | 18% | 0% | 87% |

## Perception probes: can the model even read the image?

No reasoning needed: these only ask the model to read what is printed on the image. Low scores here mean failures elsewhere start with perception, not reasoning.

| Probe | hf:Qwen/Qwen2.5-VL-3B-Instruct |
|---|---|
| Read village labels (map) | 50% (n=4) |
| Read village labels (satellite) | 25% (n=4) |
| Read pond spot height (map) | 100% (n=4) |
| Read monitoring labels (thermal) | 100% (n=4) |

## Traps and error diagnosis

| Model | Trap tasks | Fell for a trap | Most common errors |
|---|---|---|---|
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 98 | 27% | missed_some (52), extra_unrelated (21), wrong_choice (19), overestimate (13) |

Tasks a majority of real models answered correctly WITHOUT the image: 19

## Cost

| Model | Input tokens | Output tokens | USD | Mean latency (s) |
|---|---|---|---|---|
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 168420 | 2857 | 0 | 6.69 |

![skills](chart_accuracy_by_skill.png)

![eye exam](chart_eye_exam.png)

![styles](chart_by_style.png)
