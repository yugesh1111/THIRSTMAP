# Independent verification

This file is produced by `verify_results.py`, which does not reuse the report code and checks the scorer with parsers of its own.

> **Important:** the models named `mock:*` are offline *baselines* used to test the dataset and the
> scorer: `oracle` returns the answer key, `random` picks random options, `stubborn` repeats the
> original answer on counterfactual twins. They are **not** AI models. Real open-weight models are
> checked in section 1b, open models and Gemini alike.

## 1. Reported accuracies recomputed from raw responses

| Model | Mode | Responses | Recomputed | In summary.json | Match |
|---|---|---|---|---|---|
| mock:oracle | blind | 5761 | 100.00% | 100.00% | ✅ |
| mock:oracle | image | 5761 | 100.00% | 100.00% | ✅ |
| mock:random | blind | 5761 | 13.97% | 13.97% | ✅ |
| mock:random | image | 5761 | 13.68% | 13.68% | ✅ |
| mock:stubborn | blind | 5761 | 87.16% | 87.16% | ✅ |
| mock:stubborn | image | 5761 | 87.16% | 87.16% | ✅ |

**All reported accuracies reproduced exactly: yes.**

## 2. Random baseline vs exact chance

Expected correct by pure chance (computed from each task's options): **796.4** of 5761 (13.8%). Observed: **788** (13.7%). Difference = -0.33 standard deviations (consistent with chance).

| Question type | Tasks | Expected | Observed |
|---|---|---|---|
| Q1 | 767 | 2.6% | 3.4% |
| Q2 | 775 | 17.2% | 17.7% |
| Q3 | 614 | 25.0% | 23.8% |
| Q4 | 308 | 4.9% | 4.9% |
| Q5 | 578 | 12.5% | 11.2% |
| Q6 | 606 | 33.3% | 32.8% |
| Q7 | 914 | 4.3% | 4.0% |
| Q8 | 305 | 9.8% | 10.8% |
| Q9 | 278 | 20.0% | 21.9% |
| Q10 | 616 | 12.3% | 11.2% |

## 1b. Real model answers (results/models)

These are free-text replies from real models, so a second parser, written separately from the project's scorer, re-reads every raw reply. *Agreement* is how often the two parsers reach the same verdict; disagreements are listed so they can be judged by eye.

Compared on the 144 tasks that every model answered with the image.

| Model | Mode | Replies | Project scorer on raw replies | In summary.json | Second parser | Agreement |
|---|---|---|---|---|---|---|
| hf:HuggingFaceTB/SmolVLM-256M-Instruct | blind | 144 | 9.7% | 9.7% ✅ | 9.7% | 100.0% |
| hf:HuggingFaceTB/SmolVLM-256M-Instruct | image | 144 | 7.6% | 7.6% ✅ | 8.3% | 99.3% |
| hf:HuggingFaceTB/SmolVLM2-2.2B-Instruct | blind | 144 | 11.8% | 11.8% ✅ | 11.8% | 100.0% |
| hf:HuggingFaceTB/SmolVLM2-2.2B-Instruct | image | 144 | 8.3% | 8.3% ✅ | 8.3% | 100.0% |
| hf:Qwen/Qwen2-VL-2B-Instruct | blind | 144 | 9.0% | 9.0% ✅ | 9.0% | 100.0% |
| hf:Qwen/Qwen2-VL-2B-Instruct | image | 144 | 8.3% | 8.3% ✅ | 8.3% | 100.0% |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | blind | 144 | 13.2% | 13.2% ✅ | 13.2% | 100.0% |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | image | 144 | 16.0% | 16.0% ✅ | 16.0% | 100.0% |

**1 replies where the two parsers disagree** (first 12):

| Model | Task | Key | Raw reply | Project scorer |
|---|---|---|---|---|
| SmolVLM-256M-Instruct | level5_seed76732_cf__Q8__thermal | [] | `{ "answer": [["V1", "V4"], ["M1", "M2"]]}` | wrong |

Ten random raw replies, exactly as the models wrote them:

| Model | Task | Key | Raw reply | Scored |
|---|---|---|---|---|
| SmolVLM-256M-Instruct | level4_seed44229__Q4__map | ['F1', 'F3', 'F4', 'F5'] | `{ "answer": [ { "label": "V1", "unit": "V1", "unit_length": "125 m", "unit_width": "125 m"` | ❌ |
| Qwen2-VL-2B-Instruct | level1_seed100250__Q10__map | 1690 | `{"answer": 100}` | ❌ |
| SmolVLM-256M-Instruct | level3_seed47829_cf__Q7__satellite | ['V2'] | `{ "answer": [] }` | ❌ |
| Qwen2.5-VL-3B-Instruct | level5_seed77508__Q5__map | SW | ````json {"answer": "E"} ```` | ❌ |
| Qwen2.5-VL-3B-Instruct | level5_seed54139__Q7__satellite | ['V1', 'V3'] | `{"answer": ["V3"]}` | ❌ |
| SmolVLM2-2.2B-Instruct | level3_seed47829_cf__Q7__satellite | ['V2'] | `{"answer": ["V5", "V6", "V3", "V2", "V1"]}` | ❌ |
| Qwen2.5-VL-3B-Instruct | level4_seed45587_cf__Q8__thermal | [] | `{"answer": ["M2"]}` | ❌ |
| SmolVLM-256M-Instruct | real_navi_mumbai_seed32379_cf__Q7__map | ['V4'] | `{ "answer": [ { "label": "V1", "source": "V3", "unit": "m", "unit_score": "1", "unit_score` | ❌ |
| Qwen2.5-VL-3B-Instruct | level2_seed21111__Q7__satellite | ['V2'] | `{"answer": ["V2"]}` | ✅ |
| Qwen2.5-VL-3B-Instruct | level5_seed76732__Q6__map | S3 | ````json {"answer": "S2"} ```` | ❌ |

## 1b. Real model answers (results/frontier)

These are free-text replies from real models, so a second parser, written separately from the project's scorer, re-reads every raw reply. *Agreement* is how often the two parsers reach the same verdict; disagreements are listed so they can be judged by eye.

Compared on the 89 tasks that every model answered with the image.

| Model | Mode | Replies | Project scorer on raw replies | In summary.json | Second parser | Agreement |
|---|---|---|---|---|---|---|
| hf:Qwen/Qwen2-VL-2B-Instruct | image | 89 | 5.6% | 5.6% ✅ | 5.6% | 100.0% |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | image | 89 | 11.2% | 11.2% ✅ | 11.2% | 100.0% |
| openai:gemini-3.1-flash-lite | image | 89 | 46.1% | 46.1% ✅ | 46.1% | 100.0% |
| openai:gemini-3.5-flash-lite | image | 89 | 39.3% | 39.3% ✅ | 39.3% | 100.0% |

Ten random raw replies, exactly as the models wrote them:

| Model | Task | Key | Raw reply | Scored |
|---|---|---|---|---|
| openai:gemini-3.5-flash-lite | real_chennai_seed39037__Q6__map | S2 | `{"answer": "S2"}` | ✅ |
| openai:gemini-3.1-flash-lite | real_chennai_seed39037__Q7__map | ['V1'] | `{"answer": ["V1", "V5"]}` | ❌ |
| Qwen2.5-VL-3B-Instruct | level4_seed58903__Q10__map | 2550 | `{"answer": 1000}` | ❌ |
| Qwen2-VL-2B-Instruct | real_chennai_seed31409__Q3__satellite | A | `{"answer": "B"}` | ❌ |
| openai:gemini-3.1-flash-lite | level4_seed58903__Q10__map | 2550 | `{"answer": 3400}` | ❌ |
| openai:gemini-3.1-flash-lite | level3_seed34416__Q9__thermal | 6.7 | `{"answer": 9}` | ❌ |
| Qwen2-VL-2B-Instruct | level2_seed22760__Q10__map | 2210 | `{"answer": 4}` | ❌ |
| openai:gemini-3.1-flash-lite | level3_seed31409_cf__Q7__map | ['V4'] | `{"answer": ["V4"]}` | ✅ |
| Qwen2.5-VL-3B-Instruct | real_navi_mumbai_seed31312__Q1__satellite | ['V4', 'V5'] | `{"answer": ["V1", "V4"]}` | ❌ |
| Qwen2-VL-2B-Instruct | level3_seed58561__Q6__satellite | S1 | `{"answer": "B"}` | ❌ |

## 3. Dataset regenerated from recorded seeds

| Scene | Answer key identical | Images identical |
|---|---|---|
| level1_seed26942 | ✅ | ✅ (6 images) |
| level2_seed38986 | ✅ | ✅ (6 images) |
| level3_seed42820 | ✅ | ✅ (6 images) |
| level5_seed77508 | ✅ | ✅ (4 images) |
| level3_seed43499 | ✅ | ✅ (6 images) |
| level4_seed44326 | ✅ | ✅ (6 images) |
| level5_seed59342 | ✅ | ✅ (6 images) |
| level1_seed22224 | ✅ | ✅ (6 images) |
| level5_seed61312 | ✅ | ✅ (6 images) |
| level2_seed23245 | ✅ | ✅ (4 images) |

**10/10 sampled scenes regenerated byte-for-byte from code + seed.**

## 4. Spot-check sheets

Six random tasks: what the model sees (left) next to the answer reveal (right), with the question and key.

![spot check 1](spotcheck_1.png)
![spot check 2](spotcheck_2.png)
![spot check 3](spotcheck_3.png)
![spot check 4](spotcheck_4.png)
![spot check 5](spotcheck_5.png)
![spot check 6](spotcheck_6.png)
