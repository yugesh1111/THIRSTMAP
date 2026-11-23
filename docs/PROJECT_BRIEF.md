# ThirstMap — Project Brief
*Innodata AI Hackathon · Track 2: Visual Task Factory · updated 23 Nov 2026*

---

## 1. The punchline

> **"AI is drinking India's water. We tested whether AI can even see where that water goes."**

Alternative for the demo:
> *"India's data centres may need ~358 billion litres of water a year by 2030. We showed four open AI vision models a map and asked one question: where does the wastewater go? None of them did better than random guessing, and none got both halves of a single before-and-after pair right."*
> (real results: [`FINDINGS.md`](FINDINGS.md); frontier API models still to be run)

**Title:** *ThirstMap — can AI trace water through the landscape?*

---

## 1b. Fit to the Track 2 brief (checked line by line against the official text)

**The big question they ask:** *"Which visual capabilities matter most in real-world applications, and how can we reliably test whether advanced AI models possess them?"*

**Our answer:** the capability to **trace connected flow through terrain imagery** — following a branching network, reading 3-D relief from a 2-D picture, telling *near* from *connected*, and reading colour scales — because environmental-impact, disaster and infrastructure decisions (here: AI data-centre water) depend on it, and AI geospatial agents are starting to make those calls.

| Brief says | ThirstMap | ✔ |
|---|---|---|
| Pick an image family and a real-world visual problem | Terrain imagery (satellite-style, topographic map, thermal) · where a data centre's water comes from and goes | ✅ |
| Generate **synthetic** images and questions | Every image is rendered by our code from a scene script (real elevation can be an *input*, the image is still generated) | ✅ |
| Reference answers checked **without the tested model** | Water-flow simulation + independent second implementation (pysheds) + unit tests | ✅ |
| Evaluate advanced multimodal models; strengths & weaknesses | Four open models evaluated for real (per skill, style, difficulty, trap, pairs, appearance, reading checks, vs exact chance); Claude / GPT / Gemini adapters ready for API keys | ✅ open models, ⏳ frontier |
| *Stand out:* every question needs genuine visual understanding | Answers exist only in the picture; every question is also asked without the image (V13) | ✅ |
| *Stand out:* each image holds enough evidence | Pixel-level path-visibility + label-legibility validators; questions only asked in styles that show the evidence | ✅ |
| *Stand out:* vary visual relationships and reasoning, **not just count** | Trace, order, connectivity vs proximity, elevation comparison, direction, siting, catchment, colour-scale reading — no counting tasks at all | ✅ |
| *Stand out:* explain why errors matter in the real application | Wrong village / wrong wetland / false "site is safe" (section 2) | ✅ |
| *Submit:* reusable generation + evaluation pipeline | `generate` → `validate` → `evaluate` → `report`, seed + difficulty driven; `run_all.sh`; CI on every push | ✅ |
| *Submit:* sample tasks with validation evidence | 5,761-task dataset (release), `dataset_sample/`, `eval_set/`, VALIDATION_REPORT.md, VERIFICATION.md | ✅ |
| *Submit:* findings on model strengths/weaknesses | FINDINGS.md: accuracy vs chance with p-values, per-skill profile, pairs, appearance, reading checks, fine-tuning | ✅ |
| *Submit:* **a demo where scoring separates right from wrong** | `docs/demo/index.html`: image → question → real model replies → auto ✓/✗ → answer reveal, beside answer-key and random baselines | ✅ |
| *Their example:* "your code draws a bar chart, so it already knows which bar is tallest" | Same principle: our code builds the terrain, so it already knows where every drop of water goes | ✅ |
| FAQ: clean repo, sample outputs, automated tests/benchmarks/metrics, architecture + demo | 41 tests, CI, ARCHITECTURE.md, demo, reports | ✅ |
| FAQ: no API keys in code | Keys only via environment variables | ✅ |
| FAQ: organiser-provided model API access | Harness supports Claude, OpenAI-compatible, Gemini and Hugging Face models + offline baselines | ✅ ready |

**Verdict: the topic fits the brief well. No title change needed** — only the subtitle above, which states the visual capability in the brief's own terms.

Note: the evaluation-criteria text on the page shows Track 1 wording (repository, reference implementations). For Track 2 we map them as: *Implementation* = pipeline runs end to end and generalises (any seed/level/terrain); *Validity* = solvable tasks, independently verified answers, evidence checks; *Variation* = different reasoning skills and image styles, not reworded questions.

---

## 2. The problem — and why it is a real problem

**AI's water footprint is growing fast, mostly in places that are already short of water.**

| Fact | Source |
|---|---|
| Indian data centres use ~150 billion litres/year (2024-25), projected ~358 billion by 2030 (estimate) | Down To Earth, citing CEEW-linked study |
| Mumbai + Chennai hold ~70% of India's data-centre capacity — both water-stressed cities | Down To Earth |
| Hyderabad faces a projected 870 million litres/day water deficit by 2027 | Down To Earth |
| 60–80% of India's data centres projected to face high/extremely-high water stress within the decade; 43% of data centres worldwide already sit in high water-stress areas | S&P Global |
| **None of India's 15 state data-centre policies require water-stress mapping for environmental clearance** | Down To Earth |
| Water is often the last consideration in data-centre siting | Bloomberg |
| Regulators and communities "lack tools to verify infrastructure impacts" | University of Minnesota, *AI's Hidden Thirst* |
| Globally, AI could use as much water as 1.3 billion people by 2030 | UN University report (via TIME) |

**The gap:** the question that matters locally — *"where does this facility's water come from, where does its warm wastewater go, which villages and farms are affected, and where could nature clean it?"* — is a question about **terrain and water flow**, answered by reading **maps and satellite imagery**.

**Why AI enters the picture:** AI geospatial agents are being built to answer exactly these questions from imagery (e.g. Google's Gemini-based *Earth AI Geospatial Reasoning agent*, currently experimental and expanding access). Planners, journalists, ESG analysts and citizens already paste maps into chatbots and ask "is this safe?".

**Why errors matter:**
- AI says "no village downstream" when there is one → a facility is approved, a village's drinking-water source gets warm, chemical-laden blowdown.
- AI puts a treatment wetland in the wrong place → money spent, water still uncleaned.
- AI says a site is safe on the wrong side of a ridge → false reassurance in an environmental review.

**Our project does not build that AI. It builds the exam that tells us whether such AI can be trusted.**

---

## 3. What exactly we are building

An **automated pipeline** (the hackathon's "Visual Task Factory") that produces, with no human in the loop:

```
seed + difficulty level
   │
   ▼
1. SCENE SCRIPT ─ terrain (elevation grid) + water-flow simulation + placements
   │              (AI data centre, outfall O, villages + water intakes, farms,
   │               treated-water pond P, candidate wetland sites A–D)
   ▼
2. IMAGES ─ the same scene rendered in 3 styles
   │   🛰️ satellite-style image   🗺️ topographic map   🌡️ thermal false-colour
   ▼
3. QUESTIONS + ANSWER KEY ─ computed from the scene script, never from an AI
   ▼
4. VALIDATORS ─ discard any task that is ambiguous, unreadable, or answerable without the image
   ▼
5. EVALUATION ─ send image + question to frontier models, score automatically
   ▼
6. "EYE EXAM" ─ difficulty dial 1–5 finds each model's breaking point per skill
   ▼
7. REPORT ─ accuracy by skill / image style / difficulty, traps fallen for, examples
```

### 3.1 Exactly how the images are generated

**Step 1 — Terrain (elevation grid, 160×160 cells, 25 m per cell = 4 km × 4 km).**
- *Synthetic mode:* fractal noise (spectral synthesis) + a north→south regional slope. Roughness and hill height come from the difficulty level.
- *Real-terrain mode:* a crop of the **Copernicus DEM (30 m)** around a real Indian location (e.g. near Chennai, Hyderabad).

**Step 2 — Water-flow simulation (this is where answers come from).**
1. *Priority-flood* fills depressions so every drop of water has a path out (deep fills become lakes).
2. *D8 routing:* each cell sends its water to its steepest downhill neighbour.
3. *Flow accumulation:* how many cells drain through each cell → stream size; above a threshold = visible stream.
4. *Trace:* follow water from any point (e.g. outfall O) to where it leaves the region.

**Step 3 — Placements (the "scene script").** The program places the data centre on dry land, its outfall O on a lower tributary, villages with water intakes on streams (some downstream of O, some deliberately as **traps**: same stream but *upstream*, or very close to the data centre but on *another* stream), wetland candidates (one correct, one "too late" after a village, others on wrong streams), a pond and farms (with a ±3 m elevation margin from the pond).

**Step 4 — Rendering, three styles from one scene:**
| Style | What it looks like | What the AI must use |
|---|---|---|
| 🛰️ **Satellite-style** (main) | Looks like imagery from space: relief shading, dry scrub, crop-field mosaic, riparian vegetation along streams, sandy riverbeds, village rooftops, data-centre roofs + cooling towers, annotation labels | Read terrain from shading, follow channels and vegetation lines |
| 🗺️ **Topographic map** | Hillshade + contour lines + streams + symbols | Read contours (elevation), follow streams |
| 🌡️ **Thermal false-colour** | Colour = water temperature; warm plume spreading downstream from O, with colour legend | Read the colour scale + scale bar, follow the plume |

All three share **one answer key**, which lets us ask: *does the AI understand the land, or only map symbols?*

### 3.2 The questions (each declares which image styles contain enough evidence)

| # | Skill | Example | Styles | Status |
|---|---|---|---|---|
| Q1 | Trace downstream | Which villages receive DC-1's wastewater? | map, satellite | ✅ built |
| Q2 | Order along flow | Which village receives it first? | map, satellite | ✅ built |
| Q3 | Nature-based filtering | Which wetland site (A–D) cleans ALL wastewater before ANY village? | map, satellite | ✅ built |
| Q4 | Read elevation | Which farms lie lower than pond P (gravity-fed reuse)? | map only (needs contours) | ✅ built |
| Q5 | Flow direction | Which way does the stream flow below O? | map, satellite | ✅ built |
| Q6 | Siting | Of sites S1–S3, whose wastewater reaches no village? | map, satellite | ✅ built |
| Q7 | Water competition | DC-1 draws from intake I — which villages share the same water (upstream catchment)? | map, satellite | ✅ built |
| Q8 | Colour-scale threshold | At which monitoring points is the water > 3 °C warmer? | thermal | ✅ built |
| Q9 | Colour-scale value | How many °C warmer is the water at M2? | thermal | ✅ built |
| Q10 | Measure along a winding path | How far (m) does the wastewater travel along the stream to the first village? | map, satellite | ✅ built |

**Built-in traps:** upstream village on the same stream · near-but-other-stream village · wetland after a village ("too late") · ridges that separate close points · monitoring points upstream or on other streams.

---

## 4. Generated data vs real data — what is allowed?

**What the brief says:** *"Build an automated pipeline that **generates synthetic images**, questions about those images, and verifiable reference answers… Teams choose their image family, application domain, and generation approach."* and *"Generate synthetic images and questions about them."*

**So: the scored benchmark must be synthetic images.** Real data is allowed as an *ingredient* (real elevation, land cover, water) because the image is still generated by our pipeline and the answer is still computed. Real satellite photos are **not** part of the scored benchmark.

**Our plan:**

| Mode | Images | Answers | Role in the project |
|---|---|---|---|
| **A. Fully synthetic** | Generated by our renderer | Our simulation | **Core benchmark** (unlimited, fully controlled, difficulty dial) |
| **B. Real terrain, synthetic scene** | Generated by our renderer from **real Copernicus elevation + real ESA WorldCover land cover + real JRC water** for an Indian location; DC/villages are *hypothetical* placements | Same simulation on the real terrain | **Realism check:** do model results on real geography match synthetic results? |
| **C. Real satellite photos** (Sentinel-2) | Real imagery, our annotations | Simulation on aligned real DEM | **Stretch goal, appendix only** — not part of the scored synthetic benchmark (brief asks for synthetic images) |

The images are always produced by our pipeline and every answer is computed, so "synthetic images + verifiable answers" holds in A and B. Real data makes the scenes **more realistic and more convincing**, not less valid. **We never claim that a real data centre harms a real village** — placements in mode B are hypothetical.

---

## 5. Real data sources (free)

Reachability = tested from our build environment today (✅ downloads work here · ❌ blocked here, use from a laptop).

| Data | What it gives us | Licence / access | Reachable here | Used for |
|---|---|---|---|---|
| **Copernicus DEM GLO-30** | Global elevation, 30 m | Free (Copernicus terms); AWS open data bucket `copernicus-dem-30m`, no account | ✅ (tested a tile near Chennai) | Real-terrain mode (B), hydrology cross-check |
| **ESA WorldCover 10 m** | Land cover (trees, crops, built-up, water…) | CC BY 4.0; AWS `esa-worldcover` | ✅ | Realistic colours/textures in satellite style (B) |
| **JRC Global Surface Water** | Where water has been present 1984–present | Free, "Source: EC JRC/Google"; Google Cloud Storage | ✅ | Real lakes/rivers; check our simulated rivers against real ones |
| **Sentinel-2 (L2A COGs)** | Real 10 m satellite imagery | Free (Copernicus); AWS `sentinel-cogs` | ✅ (bucket reachable) | Optional real-photo probe (C) |
| **Landsat 8/9 Collection 2 surface temperature** | Real thermal imagery (30 m, from 100 m) | Free (USGS); also via Copernicus Data Space | ❌ USGS blocked here | Reference for realistic thermal styling |
| **HydroSHEDS / HydroRIVERS** | Global river network & watersheds | Free incl. commercial | ❌ blocked here | Cross-check real-terrain stream networks |
| **OpenStreetMap** (`telecom=data_center`, `industrial=data_centre`) | Real data-centre locations | ODbL | ❌ Overpass blocked here | Pick realistic regions for mode B |
| **DataCenterMap** (India city pages) | Directory of Indian data centres (e.g. 29 in Chennai) | Commercial directory — view only | n/a | Choose realistic regions only |
| **WRI Aqueduct 4.0** | Basin-level water-stress scores | Free | n/a | Context: which regions are high-stress |
| **India-WRIS / Bhuvan (ISRO)** | Indian basins, watersheds, rivers; Cartosat DEM (~32 m, login) | Free with login | not tested | Optional India-specific layers |

Python tooling: **pysheds** (✅ installable here), WhiteboxTools — independent hydrology implementations for validation.

---

## 6. Is anything like this already out there?

| Existing thing | What it does | Why it is not what we build |
|---|---|---|
| **MapBench** (2025) | Tests AI route-finding on illustrated maps (zoos, museums, trails) | No terrain, contours or water flow |
| **GEOBench-VLM** | General geospatial tasks for vision-language models | No hydrology, no data-centre/water impact |
| **FloodVL-Pix** (2026) | AI describes floods that *already happened* in satellite images | Observation, not prediction of where water will go |
| **Google Earth AI Geospatial Reasoning agent** | Gemini agent answering geospatial questions (incl. flood hydrology) | It is an *AI to be tested*; experimental; Google evaluates it on its own benchmark |
| **WRI Aqueduct**, S&P analysis, IEEE PESGM-2026 siting framework | Basin- or state-level water-stress scoring for siting | Not local flow, not an AI test |
| **UMN "AI's Hidden Thirst"** dashboard | Models how AI workloads translate into water stress | Decision-support tool, not an AI test |
| Industry (Xylem, Gradiant…) | Water management services for data centres | Operations, not evaluation |

**Conclusion from our searches:** we found **no benchmark that tests whether AI can read local water flow from images, and none tied to data-centre water impact.** (Searches are not exhaustive; we state this honestly.)

---

## 7. Validation — how we prove every task is correct

This is the core of the project (25% of the score is validity, and it is why we chose this over pose/yoga). Every generated task must pass **all** checks or it is **discarded, never hand-edited**.

### 7.1 Is the answer correct? (answer-key validity)
| Check | How | Pass rule |
|---|---|---|
| **V1 Two independent implementations** | Compute flow paths/catchments with our code **and** with an independent library (pysheds) on the same elevation grid | Answers must agree, else discard |
| **V2 Known-answer unit tests** | Hand-built terrains with obvious answers: tilted plane, V-shaped valley, two valleys split by a ridge, a closed bowl | Pipeline must return the known answer (pytest) |
| **V3 Counterfactual pairs** ✅ built | Every scene gets a twin with one minimal change (outfall moved / intake moved / water temperature changed); 740 linked pairs in the dataset; twins are re-validated independently | The answer must change; models are scored on **pair accuracy** (both versions right) |
| **V4 Determinism** | Same seed + level → byte-identical scene and answers | Re-run check in CI |

### 7.2 Is the answer unambiguous? (no borderline cases)
| Check | Rule |
|---|---|
| **V5 Elevation margin** | Farms within ±3 m of the pond are never asked about |
| **V6 Direction margin** | Flow direction not asked if within 7° of a compass-sector boundary |
| **V7 Spatial margin** | "Unaffected" villages must be ≥5 cells from the wastewater path; markers spaced ≥6–12 cells apart |
| **V8 Single correct wetland** | Exactly one candidate lies between O and the first village |

### 7.3 Does the image actually contain the evidence? (sufficiency)
| Check | How |
|---|---|
| **V9 Path visibility** | Sample the rendered image along the answer path — the stream must be visible (colour/width check) in that style |
| **V10 Label legibility** | All labels ≥ minimum pixel size and no overlapping bounding boxes |
| **V11 Style applicability** | Questions are only asked in styles that contain the evidence (e.g. elevation comparison only where contours exist) |
| **V12 Real-terrain sanity** | In mode B, simulated rivers should overlap JRC observed water |

### 7.4 Does the task really need the image? (no shortcuts)
| Check | How | Pass rule |
|---|---|---|
| **V13 Blind baseline** | Ask models the question **without the image** | Near chance level; tasks blind models answer correctly too often are flagged |
| **V14 Answer balance** | Distribution of correct letters/villages/directions | No answer position wins by default |
| **V15 Human solvability** | Team members answer a random sample per difficulty level | Humans ≥ 95% correct; disagreements investigated |

### 7.5 Measuring the AI models
- Automatic scoring: exact match (single answers), set F1 (lists), tolerance (distances/temperatures).
- Per **skill**, per **image style**, per **difficulty level**, per **trap**.
- **Eye exam:** accuracy vs difficulty curve per skill; "breaking point" = level where accuracy falls below 50%. Optional adaptive staircase (harder after correct, easier after wrong) to save API cost.
- Compare against blind baseline and human score.

---

## 8. Honest limitations
- Synthetic terrain is simplified; D8 routing ignores groundwater, canals, pipes, seasonality.
- Copernicus DEM is a surface model (includes trees/buildings) — fine for rural terrain, imperfect in cities.
- Thermal plume will use a simplified mixing model, not a full hydrodynamic model.
- Real-terrain scenes use **hypothetical** facility placements.
- Several impact statistics come from secondary reporting and are estimates.

---

## 9. Plan (13 days to 6 Dec)
| Days | Work |
|---|---|
| 1–3 | Satellite renderer · thermal renderer · Q6–Q8 · module refactor (started) |
| 3–5 | Validators V1–V15 · unit tests · batch generation (hundreds of tasks, levels 1–5) · real-terrain mode B |
| 5–8 | Evaluation harness · run frontier models · blind baseline · human spot check |
| 8–11 | Eye-exam analysis · charts · failure gallery |
| 11–13 | README, architecture write-up, demo video, submission |

**Needed from the team:** (1) the Track-2 "Read more" text, (2) which model APIs/keys we have (organiser credits?), (3) 2–3 people for the human spot check.

---

## Sources
- Down To Earth — India's AI data centres are draining water: https://www.downtoearth.org.in/water/india-is-using-water-to-build-the-machines-that-tell-us-we-are-running-out-of-it
- Down To Earth — Thirsty data centres, thin regulation: https://www.downtoearth.org.in/science-technology/thirsty-data-centres-thin-regulation-who-is-watching-indias-water
- Outlook — AI Impact Summit 2026, water stress from data centres: https://www.outlookindia.com/national/ai-impact-summit-2026-water-stress-from-data-centres-a-cause-for-concern
- CEEW data-centre study: https://www.ceew.in/sites/default/files/ceew-data-centre-study-web-ready-final.pdf
- S&P Global — Beneath the surface: water stress in data centers: https://www.spglobal.com/sustainable1/en/insights/special-editorial/beneath-the-surface-water-stress-in-data-centers
- Bloomberg — AI is draining water: https://www.bloomberg.com/graphics/2025-ai-impacts-data-centers-water-data/
- University of Minnesota — AI's hidden thirst: https://environment.umn.edu/research/projects/ais-hidden-thirst
- TIME — UN report on AI water use: https://time.com/article/2026/06/03/ai-global-water-resources-un-report/
- IEEE PESGM 2026 water-carbon siting framework: https://index.mirasmart.com/PESGM2026/PDFfiles/PESGM2026-001928.pdf
- GMF — Water and the AI infrastructure boom: https://www.gmfus.org/news/water-and-ai-infrastructure-boom
- Data Center Frontier — Rethinking water in the AI data center era: https://www.datacenterfrontier.com/sustainability/article/55353238/rethinking-water-in-the-ai-data-center-era
- Ramboll — Using water wisely in data centres (constructed wetlands): https://www.ramboll.com/en-gb/insights/decarbonise-for-net-zero/how-to-use-water-wisely-in-data-centres
- Google Research — Earth AI Geospatial Reasoning agent: https://research.google/pubs/google-earth-ai-geospatial-reasoning-agent-capabilities-and-a-systematic-evaluation/
- Google Research — Geospatial agents blog: https://research.google/blog/putting-earth-ai-to-work-geospatial-agents-for-our-planets-biggest-challenges/
- MapBench: https://arxiv.org/pdf/2503.14607 · GEOBench-VLM: https://arxiv.org/pdf/2411.19325 · FloodVLM-Pix: https://arxiv.org/html/2610.23377
- Copernicus DEM on AWS: https://registry.opendata.aws/copernicus-dem/ · Copernicus Data Space COP-DEM: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- HydroRIVERS: https://hydrosheds.org/page/hydrorivers
- ESA WorldCover: https://worldcover2021.esa.int · JRC Global Surface Water: https://global-surface-water.appspot.com/download
- Landsat C2 surface temperature (USGS): https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature · Landsat in Copernicus Data Space: https://dataspace.copernicus.eu/node/3092
- WRI Aqueduct: https://www.wri.org/data/aqueduct-water-risk-atlas
- OSM data-centre tagging: https://wiki.openstreetmap.org/wiki/Tag:telecom%3Ddata_center · DataCenterMap Chennai: https://datacentermap.com/india/chennai
- Bhuvan free data: https://bhuvan.nrsc.gov.in/wiki/index.php/Free_Satellite_Data_Download · India-WRIS (CWC): https://cwc.gov.in/en/water-resources-information-system-wris
- pysheds: https://github.com/mdbartos/pysheds · WhiteboxTools hydrology: https://jblindsay.github.io/wbt_book/available_tools/hydrological_analysis.html
