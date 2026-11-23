# Before AI screens water impact, it should pass a twin test

*A half-page note for regulators, planners and ESG teams. Evidence: [`FINDINGS.md`](FINDINGS.md).*

**The situation.** India's data centres are growing fastest in cities already short of water (about 70% of
capacity sits in Mumbai and Chennai), and none of the 15 state data-centre policies requires water-stress mapping
for clearance ([Down To Earth](https://www.downtoearth.org.in/science-technology/thirsty-data-centres-thin-regulation-who-is-watching-indias-water)).
AI geospatial assistants are being built and used to answer exactly the questions such mapping would ask: where
does a facility's wastewater go, which villages share its water source, where could a wetland clean it.

**What we measured.** ThirstMap generates landscapes whose water flow is simulated, so every answer is known and is
re-checked by an independent library. On the same questions, small open models scored at chance level, and Gemini
Flash-Lite models scored about three times chance (48% and 40% against 14% by chance, on the same 83 questions). But every scene also has a *twin* that changes one
thing (for example, the outfall moves to another stream) so that the correct answer changes. **No model, Gemini included, got
both the original and its twin right in a single pair (0 of 7 pairs).** A tool that cannot get both right is not yet
tracing where the water flows.

**Why it matters.** Each wrong answer has a cost on the ground. In our runs, real model errors would have left
villages that receive warm wastewater unwarned, raised false alarms for villages on other streams, approved
siting options whose wastewater reaches a village (Gemini did so 14 times), and placed wetlands after the water had already reached people.

**Recommendation.** Treat AI answers about water flow as unverified until the tool passes a counterfactual test
like this one on imagery of the kind it will see:
1. **Pair test:** both halves right on at least 90% of before-and-after pairs (no current model passes).
2. **Above-chance accuracy** on every skill used for a decision, reported with the chance level and sample size.
3. **Published inputs:** the exact images and questions used, so the result can be repeated.

ThirstMap is open (MIT code, CC BY 4.0 data) and runs any model with one command: https://github.com/yugesh1111/THIRSTMAP
