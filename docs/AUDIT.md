# Dataset audit

**431 of 5761 tasks (7.5%) are excluded** from every score, the evaluator, the demo and the human test (`dataset/errata.jsonl`). Both problems were found by drawing model answers on the images they saw (`overlays.py`), and both are fixed for new builds (checks version 2) while dataset v1.0 still rebuilds byte for byte.

## Check V10b: labels hidden under the scale bar, north arrow or legend

Dataset v1.0 was built before check V10b existed. `audit_labels.py` rebuilt every scene from its seed, re-rendered each image style exactly as built, and looked for option labels drawn under an area painted over the map afterwards: the 1 km scale bar, the north arrow, and (thermal) the colour legend. A hidden label can make a question unanswerable, so every such task is listed in `dataset/errata.jsonl` and left out of every score, the evaluator, the demo and the human test. New builds run V10b during generation: labels are placed clear of those areas, and a question whose labels are still hidden is dropped.

- Scene folders checked: **614** (0 could not be rebuilt)
- Images re-rendered: **1398**, pixel-identical to the published image: **1398**
- Tasks with a hidden option label: **315** of 5761 (5.5%), in 102 scenes; the correct answer itself hidden in 44

| Style | Tasks excluded | Examples |
|---|---|---|
| satellite | 157 | level1_seed19799__Q1__satellite (hidden: V2); level1_seed19799__Q2__satellite (hidden: V2); level1_seed19799__Q7__satellite (hidden: V2) |
| map | 138 | level1_seed19799__Q1__map (hidden: V2); level1_seed19799__Q2__map (hidden: V2); level1_seed19799__Q7__map (hidden: V2) |
| thermal | 20 | level1_seed78239__Q8__thermal (hidden: M2); level1_seed15469__Q8__thermal (hidden: M4); level2_seed21111__Q8__thermal (hidden: M2) |

Found when the overlay of a model's answer showed village V1 of `level3_seed58561_cf` under the scale bar.

## Count check: scenes with more items than their design allows

In dataset v1.0, asking the placement routine for zero more items returned every free site instead of none. Most such scenes failed validation and were regenerated, but **6 scenes** slipped through (116 tasks, base and twin): `level1_seed11589` (55 options for Q7 (design: 4)); `level2_seed46226` (53 options for Q8 (design: 4)); `level2_seed62646` (60 options for Q8 (design: 4)); `level3_seed31700` (64 options for Q8 (design: 4)); `level3_seed39037` (60 options for Q8 (design: 4)); `level3_seed98544` (61 options for Q8 (design: 4)). Their answers were still verified independently, but a level-1 map with 55 villages is not the scene the difficulty dial describes, so every task of those scenes is excluded. New builds return no items for a zero request (`tests/test_tools.py::test_zero_count_pick_returns_nothing_in_checks_v2`).

