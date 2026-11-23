# ThirstMap evaluation report

> **Note:** `mock:*` entries are offline baselines, not AI models: `oracle` returns the answer key (tests the scorer), `random` picks random options (chance level), `stubborn` repeats the original answer on counterfactual twins. Their numbers are expected by construction; see docs/VERIFICATION.md.

## Overall

| Model | With image | Without image (blind) | Tasks |
|---|---|---|---|
| mock:oracle | 100% | 100% | 5330 |
| mock:random | 14% | 14% | 5330 |
| mock:stubborn | 88% | 88% | 5330 |

431 evaluated tasks are left out of every number here: the dataset audit found them unfair (an option label under the scale bar, north arrow or legend, or a malformed scene; docs/AUDIT.md).

## Better than guessing?

Chance = expected accuracy of a random guesser on exactly these tasks (from each task's options). p = one-sided binomial test that the model beats chance.

| Model | Correct | Accuracy | Chance | p-value |
|---|---|---|---|---|
| mock:oracle | 5330/5330 | 100% | 14% | 0 |
| mock:random | 740/5330 | 14% | 14% | 0.69 |
| mock:stubborn | 4677/5330 | 88% | 14% | 0 |

### Strict check: well-formed replies only

The scorer is lenient: it accepts a correct answer even when the reply is badly formatted. Counting a reply as right only if it is also well-formed (JSON with "answer", or a plain JSON value):

| Model | Well-formed replies | Accuracy (all) | Accuracy (well-formed only) |
|---|---|---|---|
| mock:oracle | 100% | 100% | 100% |
| mock:random | 100% | 14% | 14% |
| mock:stubborn | 100% | 88% | 88% |

## Accuracy by visual skill

Tasks = distinct tasks per skill (every model answers the same ones); with 10-30 tasks per skill, differences of a few points are within noise.

| Skill | Tasks | Chance | mock:oracle | mock:random | mock:stubborn |
|---|---|---|---|---|---|
| Trace downstream | 664 | 3% | 100% | 3% | 80% |
| Order along flow | 672 | 17% | 100% | 18% | 80% |
| Measure along flow | 604 | 12% | 100% | 11% | 100% |
| Place wetland | 571 | 25% | 100% | 24% | 100% |
| Site selection | 596 | 33% | 100% | 33% | 100% |
| Trace upstream | 804 | 4% | 100% | 4% | 67% |
| Flow direction | 566 | 12% | 100% | 11% | 100% |
| Read elevation | 302 | 5% | 100% | 5% | 100% |
| Thermal threshold | 279 | 10% | 100% | 11% | 75% |
| Thermal value | 272 | 20% | 100% | 22% | 83% |

## Eye exam: breaking level (first difficulty where accuracy < 50%)

| Skill | mock:oracle | mock:random | mock:stubborn |
|---|---|---|---|
| Trace downstream | >5 | 1 | >5 |
| Order along flow | >5 | 1 | >5 |
| Measure along flow | >5 | 1 | >5 |
| Place wetland | >5 | 1 | >5 |
| Site selection | >5 | 1 | >5 |
| Trace upstream | >5 | 1 | >5 |
| Flow direction | >5 | 1 | >5 |
| Read elevation | >5 | 1 | >5 |
| Thermal threshold | >5 | 1 | >5 |
| Thermal value | >5 | 1 | >5 |

## Map vs satellite (same scene, same question)

| Model | Pairs | Both right | Only map right | Only satellite right | Both wrong |
|---|---|---|---|---|---|
| mock:oracle | 2192 | 2192 | 0 | 0 | 0 |
| mock:random | 2192 | 69 | 239 | 251 | 1633 |
| mock:stubborn | 2192 | 1936 | 0 | 0 | 256 |

## Counterfactual pairs (one minimal change that must flip the answer)

Pair accuracy counts a pair only if BOTH the original and its twin are answered correctly. 'Unchanged answer' = the model gave the same answer to both, although the correct answer changed.

| Model | Pairs | Single-task accuracy | Pair accuracy | Unchanged answer |
|---|---|---|---|---|
| mock:oracle | 653 | 100% | 100% | 0% |
| mock:random | 653 | 9% | 2% | 7% |
| mock:stubborn | 653 | 50% | 0% | 100% |

## Traps and error diagnosis

| Model | Trap tasks | Fell for a trap | Most common errors |
|---|---|---|---|
| mock:oracle | 2990 | 0% | – |
| mock:random | 2990 | 44% | missed_some (1535), wrong_choice (963), extra_unrelated (673), overestimate (589) |
| mock:stubborn | 2990 | 1% | extra_unrelated (425), missed_some (303), wrong_choice (101), overestimate (45) |

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
