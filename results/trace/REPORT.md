# Draw the water's path

The model traces the wastewater's route from outfall O as points on the image and lists the villages it reaches. A route passes when at least 80% of the drawn line lies within 4 cells (100 m) of the simulated path and the line covers at least 80% of the path. Tasks and truth: `eval_set/trace/`.

| Model | Routes | Route right | On the path (precision) | Route covered (recall) | Villages right | Villages match its own line | Pairs: both routes right |
|---|---|---|---|---|---|---|---|
| openai:gemini-3-flash-preview | 10 | **1** | 53% | 51% | 3 | 6 | 0 of 5 |
| openai:gemini-3.1-flash-lite | 10 | **0** | 27% | 23% | 3 | 1 | 0 of 5 |
| openai:gemini-3.5-flash | 8 | **3** | 69% | 62% | 1 | 5 | 0 of 4 |
| openai:gemini-3.5-flash-lite | 10 | **1** | 36% | 44% | 0 | 2 | 0 of 5 |
| openai:gemini-3.6-flash | 7 | **4** | 80% | 78% | 1 | 2 | 1 of 3 |

**Reference lines** (no model; every image):

| Line | Passes | Precision | Recall |
|---|---|---|---|
| oracle (the true path) | 22 of 22 | 100% | 100% |
| straight line south | 0 of 22 | 26% | 20% |
| straight line to the true exit | 1 of 22 | 45% | 35% |

**Answer vs route**, per reply:

| Model | Right route, right villages | Right route, wrong villages | Wrong route, right villages | Wrong route, wrong villages |
|---|---|---|---|---|
| openai:gemini-3-flash-preview | 1 | 0 | **2** | 7 |
| openai:gemini-3.1-flash-lite | 0 | 0 | **3** | 7 |
| openai:gemini-3.5-flash | 0 | 3 | **1** | 4 |
| openai:gemini-3.5-flash-lite | 0 | 1 | **0** | 9 |
| openai:gemini-3.6-flash | 0 | 4 | **1** | 2 |

**How the wrong routes went wrong:**

- openai:gemini-3-flash-preview: 5 × cut across dry land, 4 × strayed from the stream
- openai:gemini-3.1-flash-lite: 9 × cut across dry land, 1 × strayed from the stream
- openai:gemini-3.5-flash: 2 × strayed from the stream, 2 × jumped to another stream, 1 × stopped before the water leaves the area
- openai:gemini-3.5-flash-lite: 9 × cut across dry land
- openai:gemini-3.6-flash: 2 × strayed from the stream, 1 × cut across dry land

Every route drawn over its image (true route red, the model's yellow): `docs/trace/`.
