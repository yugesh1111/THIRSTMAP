# ThirstMap evaluation report

> **Note:** `mock:*` entries are offline baselines, not AI models: `oracle` returns the answer key (tests the scorer), `random` picks random options (chance level), `stubborn` repeats the original answer on counterfactual twins. Their numbers are expected by construction; see docs/VERIFICATION.md.

## Overall

| Model | With image | Without image (blind) | Tasks |
|---|---|---|---|
| mock:oracle | 100% | 100% | 2097 |
| mock:random | 14% | 12% | 2097 |
| mock:stubborn | 85% | 85% | 2097 |

## Accuracy by visual skill

| Skill | mock:oracle | mock:random | mock:stubborn |
|---|---|---|---|
| Trace downstream | 100% | 3% | 78% |
| Order along flow | 100% | 19% | 78% |
| Place wetland | 100% | 23% | 100% |
| Site selection | 100% | 33% | 100% |
| Trace upstream | 100% | 4% | 68% |
| Flow direction | 100% | 11% | 100% |
| Read elevation | 100% | 3% | 100% |
| Thermal threshold | 100% | 11% | 76% |
| Thermal value | 100% | 23% | 82% |

## Eye exam: breaking level (first difficulty where accuracy < 50%)

| Skill | mock:oracle | mock:random | mock:stubborn |
|---|---|---|---|
| Trace downstream | >5 | 1 | >5 |
| Order along flow | >5 | 1 | >5 |
| Place wetland | >5 | 1 | >5 |
| Site selection | >5 | 2 | >5 |
| Trace upstream | >5 | 1 | >5 |
| Flow direction | >5 | 1 | >5 |
| Read elevation | >5 | 1 | >5 |
| Thermal threshold | >5 | 1 | >5 |
| Thermal value | >5 | 1 | >5 |

## Map vs satellite (same scene, same question)

| Model | Pairs | Both right | Only map right | Only satellite right | Both wrong |
|---|---|---|---|---|---|
| mock:oracle | 866 | 866 | 0 | 0 | 0 |
| mock:random | 866 | 28 | 91 | 101 | 646 |
| mock:stubborn | 866 | 738 | 0 | 0 | 128 |

## Counterfactual pairs (one minimal change that must flip the answer)

Pair accuracy counts a pair only if BOTH the original and its twin are answered correctly. 'Unchanged answer' = the model gave the same answer to both, although the correct answer changed.

| Model | Pairs | Single-task accuracy | Pair accuracy | Unchanged answer |
|---|---|---|---|---|
| mock:oracle | 308 | 100% | 100% | 0% |
| mock:random | 308 | 9% | 2% | 6% |
| mock:stubborn | 308 | 50% | 0% | 100% |

## Traps and error diagnosis

| Model | Trap tasks | Fell for a trap | Most common errors |
|---|---|---|---|
| mock:oracle | 1376 | 0% | – |
| mock:random | 1376 | 43% | missed_some (697), wrong_choice (423), extra_unrelated (324), trap:downstream_not_upstream (204) |
| mock:stubborn | 1376 | 1% | extra_unrelated (195), missed_some (147), wrong_choice (55), overestimate (20) |

Tasks a majority of real models answered correctly WITHOUT the image: 0

## Cost

| Model | Input tokens | Output tokens | USD | Mean latency (s) |
|---|---|---|---|---|
| mock:oracle | 0 | 0 | 0 | 0.0 |
| mock:random | 0 | 0 | 0 | 0.0 |
| mock:stubborn | 0 | 0 | 0 | 0.0 |

![skills](chart_accuracy_by_skill.png)

![eye exam](chart_eye_exam.png)

![styles](chart_by_style.png)
