# ThirstMap evaluation report

## Overall

| Model | With image | Without image (blind) | Tasks |
|---|---|---|---|
| hf:Qwen/Qwen2-VL-2B-Instruct | 5% | – | 83 |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 12% | – | 83 |
| openai:gemini-3.1-flash-lite | 48% | – | 83 |
| openai:gemini-3.5-flash-lite | 40% | – | 83 |

6 evaluated tasks are left out of every number here: the dataset audit found them unfair (an option label under the scale bar, north arrow or legend, or a malformed scene; docs/AUDIT.md).

## Better than guessing?

Chance = expected accuracy of a random guesser on exactly these tasks (from each task's options). p = one-sided binomial test that the model beats chance.

| Model | Correct | Accuracy | Chance | p-value |
|---|---|---|---|---|
| hf:Qwen/Qwen2-VL-2B-Instruct | 4/83 | 5% | 14% | 1 |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 10/83 | 12% | 14% | 0.75 |
| openai:gemini-3.1-flash-lite | 40/83 | 48% | 14% | 1.2e-13 |
| openai:gemini-3.5-flash-lite | 33/83 | 40% | 14% | 7.6e-09 |

### Strict check: well-formed replies only

The scorer is lenient: it accepts a correct answer even when the reply is badly formatted. Counting a reply as right only if it is also well-formed (JSON with "answer", or a plain JSON value):

| Model | Well-formed replies | Accuracy (all) | Accuracy (well-formed only) |
|---|---|---|---|
| hf:Qwen/Qwen2-VL-2B-Instruct | 100% | 5% | 5% |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 90% | 12% | 12% |
| openai:gemini-3.1-flash-lite | 100% | 48% | 48% |
| openai:gemini-3.5-flash-lite | 100% | 40% | 40% |

## Accuracy by visual skill

Tasks = distinct tasks per skill (every model answers the same ones); with 10-30 tasks per skill, differences of a few points are within noise.

| Skill | Tasks | Chance | hf:Qwen/Qwen2-VL-2B-Instruct | hf:Qwen/Qwen2.5-VL-3B-Instruct | openai:gemini-3.1-flash-lite | openai:gemini-3.5-flash-lite |
|---|---|---|---|---|---|---|
| Trace downstream | 10 | 2% | 0% | 0% | 50% | 30% |
| Order along flow | 10 | 16% | 0% | 0% | 60% | 60% |
| Measure along flow | 10 | 13% | 0% | 30% | 30% | 20% |
| Place wetland | 10 | 25% | 20% | 40% | 90% | 80% |
| Site selection | 10 | 33% | 10% | 10% | 20% | 40% |
| Trace upstream | 12 | 4% | 0% | 0% | 33% | 17% |
| Flow direction | 10 | 12% | 10% | 0% | 70% | 60% |
| Read elevation | 6 | 4% | 0% | 0% | 50% | 17% |
| Thermal threshold | 2 | 12% | 0% | 50% | 50% | 0% |
| Thermal value | 3 | 20% | 0% | 33% | 0% | 33% |

## Eye exam: breaking level (first difficulty where accuracy < 50%)

| Skill | hf:Qwen/Qwen2-VL-2B-Instruct | hf:Qwen/Qwen2.5-VL-3B-Instruct | openai:gemini-3.1-flash-lite | openai:gemini-3.5-flash-lite |
|---|---|---|---|---|
| Trace downstream | 2 | 2 | 4 | 3 |
| Order along flow | 2 | 2 | 4 | 4 |
| Measure along flow | 2 | 2 | 2 | 3 |
| Place wetland | 2 | 3 | >5 | >5 |
| Site selection | 2 | 2 | 3 | 2 |
| Trace upstream | 2 | 2 | 3 | 3 |
| Flow direction | 2 | 2 | >5 | 5 |
| Read elevation | 2 | 2 | >5 | 2 |
| Thermal threshold | 3 | >5 | >5 | 3 |
| Thermal value | 2 | 2 | 2 | 3 |

## Map vs satellite (same scene, same question)

| Model | Pairs | Both right | Only map right | Only satellite right | Both wrong |
|---|---|---|---|---|---|

## Counterfactual pairs (one minimal change that must flip the answer)

Pair accuracy counts a pair only if BOTH the original and its twin are answered correctly. 'Unchanged answer' = the model gave the same answer to both, although the correct answer changed.

| Model | Pairs | Single-task accuracy | Pair accuracy | Unchanged answer |
|---|---|---|---|---|
| hf:Qwen/Qwen2-VL-2B-Instruct | 7 | 0% | 0% | 43% |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 7 | 14% | 0% | 43% |
| openai:gemini-3.1-flash-lite | 7 | 21% | 0% | 14% |
| openai:gemini-3.5-flash-lite | 7 | 7% | 0% | 29% |

## Traps and error diagnosis

| Model | Trap tasks | Fell for a trap | Most common errors |
|---|---|---|---|
| hf:Qwen/Qwen2-VL-2B-Instruct | 44 | 52% | unparseable_or_no_answer (24), missed_some (16), underestimate (11), trap:downstream_not_upstream (10) |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 44 | 27% | missed_some (24), wrong_choice (13), unparseable_or_no_answer (12), extra_unrelated (10) |
| openai:gemini-3.1-flash-lite | 44 | 16% | extra_unrelated (11), missed_some (9), wrong_choice (9), overestimate (8) |
| openai:gemini-3.5-flash-lite | 44 | 18% | extra_unrelated (12), missed_some (12), wrong_choice (8), overestimate (7) |

Tasks a majority of real models answered correctly WITHOUT the image: 0

## Cost

| Model | Input tokens | Output tokens | USD | Mean latency (s) |
|---|---|---|---|---|
| hf:Qwen/Qwen2-VL-2B-Instruct | 0 | 0 | 0 | 34.97 |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | 0 | 0 | 0 | 57.27 |
| openai:gemini-3.1-flash-lite | 0 | 0 | 0 | 7.64 |
| openai:gemini-3.5-flash-lite | 0 | 0 | 0 | 1.44 |

![skills](chart_accuracy_by_skill.png)

![eye exam](chart_eye_exam.png)

![styles](chart_by_style.png)
