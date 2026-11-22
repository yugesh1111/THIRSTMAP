# ThirstMap evaluation report

## Overall

| Model | With image | Without image (blind) | Tasks |
|---|---|---|---|
| mock:oracle | 100% | 100% | 1521 |
| mock:random | 15% | 13% | 1521 |

## Accuracy by visual skill

| Skill | mock:oracle | mock:random |
|---|---|---|
| Trace downstream | 100% | 3% |
| Order along flow | 100% | 20% |
| Place wetland | 100% | 23% |
| Site selection | 100% | 33% |
| Trace upstream | 100% | 5% |
| Flow direction | 100% | 11% |
| Read elevation | 100% | 4% |
| Thermal threshold | 100% | 12% |
| Thermal value | 100% | 25% |

## Eye exam: breaking level (first difficulty where accuracy < 50%)

| Skill | mock:oracle | mock:random |
|---|---|---|
| Trace downstream | >5 | 1 |
| Order along flow | >5 | 1 |
| Place wetland | >5 | 1 |
| Site selection | >5 | 2 |
| Trace upstream | >5 | 1 |
| Flow direction | >5 | 1 |
| Read elevation | >5 | 1 |
| Thermal threshold | >5 | 1 |
| Thermal value | >5 | 1 |

## Map vs satellite (same scene, same question)

| Model | Pairs | Both right | Only map right | Only satellite right | Both wrong |
|---|---|---|---|---|---|
| mock:oracle | 630 | 630 | 0 | 0 | 0 |
| mock:random | 630 | 25 | 66 | 84 | 455 |

## Traps and error diagnosis

| Model | Trap tasks | Fell for a trap | Most common errors |
|---|---|---|---|
| mock:oracle | 927 | 0% | – |
| mock:random | 927 | 42% | missed_some (473), wrong_choice (329), extra_unrelated (204), trap:downstream_not_upstream (120) |

Tasks a majority of real models answered correctly WITHOUT the image: 0

## Cost

| Model | Input tokens | Output tokens | USD | Mean latency (s) |
|---|---|---|---|---|
| mock:oracle | 0 | 0 | 0 | 0.0 |
| mock:random | 0 | 0 | 0 | 0.0 |

![skills](chart_accuracy_by_skill.png)

![eye exam](chart_eye_exam.png)

![styles](chart_by_style.png)
