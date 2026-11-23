# ThirstMap: 2-minute pitch

Seven slides, about 17 seconds each. The deck is a Slides artifact (results slide built from `results/frontier`); this is its script, so the team can rehearse
from the repo. Live demo to show during or after: https://yugesh1111.github.io/THIRSTMAP/

| # | Slide | Say |
|---|---|---|
| 1 | **ThirstMap** (cover) | AI is drinking India’s water. Data centres need it for cooling, and they are being built in cities already short of it. AI tools are now being asked to judge where that water goes. We built ThirstMap to test whether they can even see it. |
| 2 | **The problem** | India’s data centres could use about 358 billion litres of water a year by 2030. Seventy percent of the capacity is in Mumbai and Chennai, both short of water, and none of the fifteen state policies asks anyone to map where the water goes. AI agents are being built to answer exactly that from imagery. Can they? |
| 3 | **The task factory** | Like the brief’s bar-chart example, our code draws the picture, so it knows the answer. It builds terrain, simulates where every drop flows, places a data centre, villages and deliberate traps, then traces the answer. Ten skills, three image styles, five difficulty levels, real terrain for four cities. |
| 4 | **Validity** | You should not have to trust us. A second library recomputes every answer (99.73% agreement, 10 of 10 answers identical), we check the evidence is visible in the actual pixels, and every scene has a twin where one small change flips the answer. Fail a check and the question is dropped, never edited. |
| 5 | **Results** | On the same 89 questions, Gemini gets 39 to 46 percent right, three times the 14% guessing level; the open models are at or below guessing. But each scene has a twin where one change flips the answer, and not one model, Gemini included, got both sides of a single pair right: 0 of 9. They answer questions; they do not follow the water. |
| 6 | **Can it be learned?** | A tiny model fine-tuned on 300 of our tasks went from 10% to 19% on scenes it never saw, and now does better with the image than without: it learned to look. People answered the same questions: read the human score from `human_eval/HUMAN_RESULTS.md`. |
| 7 | **What we hand over** | Everything is open: the live demo, the code, the 5,761 tasks and the exact images every model saw, with checksums. One command rebuilds it. Before we trust AI to judge where India’s water goes, it should pass this test. |

## Demo path (if there is time)

1. Open the live demo, scroll the **How a task is made** strip: terrain → water → scene → answer → checks → twin.
2. In **Browse the tasks**, pick *Frontier check* and show Gemini getting a scene right and its twin wrong.
3. Press **Show answer key** to reveal the water path.
