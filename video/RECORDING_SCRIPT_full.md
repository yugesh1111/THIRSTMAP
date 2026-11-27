# ThirstMap film: recording script

Read every line in order, in one take, in a quiet room (a phone voice memo is fine). Leave about one second of silence between lines. If you trip, carry on and note the line number: it can be re-recorded on its own. Numbers are written the way to say them; read the words, not the line numbers. Then: python video/make_film.py --recording <your file> (any audio format) and render as usual.

## The Pitch
 1. AI is drinking India's water.
 2. So here's the question nobody was asking: can AI even see where that water goes?

## Impact · 15%
 3. India's data centres drink about 150 billion litres of water a year. By 2030? 358 billion.
 4. And seventy percent of that capacity sits in two cities already short of water: Mumbai and Chennai.
 5. Now we're building AI agents to watch over it, from maps and satellite images. And it all comes down to one question: where does the wastewater go?

## Implementation · 25%
 6. So we built a factory.
 7. Code raises a landscape, makes it rain, and follows every drop downhill. Past a data centre. Past villages. Past traps we hid on purpose.
 8. Which means it knows the answer before it ever asks the question.
 9. Then it paints the same scene three ways: satellite, map, and thermal.

## Variation · 20%
10. Ten reasoning skills. Not one of them is counting.
11. Five levels of difficulty. Real terrain from four Indian data-centre cities. Monsoon, haze, a blurry sensor. And the answer never moves.
12. Five thousand seven hundred and sixty-one tasks. Every one with a known answer.

## Originality · 15%
13. Then we did something sneaky. Every scene gets a twin.
14. Change one small thing, move the outfall to another stream, and the right answer flips.
15. A model that's really looking gets both. A model running on habit? Caught.

## Validity · 25%
16. Now, you shouldn't have to trust us. So we don't ask you to.
17. A completely separate hydrology library re-derives every answer. If it disagrees, the question is gone. Dropped. Never edited.
18. The answer has to be visible in the actual pixels, or it doesn't ship.
19. We even turned the audit on ourselves: four hundred and thirty-one unfair tasks. Found, excluded, published.
20. And every audited image rebuilds from its seed, byte for byte.

## Implementation · 25%
21. And you don't need us to run it.
22. One pip install. One command. It builds a scene and its twin, and runs every check.
23. Every check you see passing here really passed. If it hadn't, the question would be gone.

## Findings
24. So we put the models to the test. The same eighty-three questions, for everyone.
25. The open models? No better than guessing, and guessing gets you fourteen percent.
26. Gemini Flash-Lite gets forty to forty-eight percent. Hide the image, and it falls straight back to guessing. It's really reading the map.
27. And Gemini 3.5 Flash? Seventy-seven percent. Impressive.

## Findings · Originality
28. But then, the twins.
29. Same river. We just cooled the water, so no point is above three degrees any more.
30. Gemini gives the exact same answer. Two false heat alarms.
31. Across nineteen pairs, it got both halves right only six times. Every other model, two at most.

## Beyond Right Answers
32. But a right answer isn't the whole story. So we asked the models to draw the water's path.
33. Eight times, a model followed the water, then named the wrong villages. Seven times, it named the right villages along the wrong route.
34. Then we hid part of the river under a cloud, where the answer truly cannot be known.
35. Thirty-four times out of forty-two, the models made up an answer anyway. Only two models always said: I can't tell.

## Demo · Scoring
36. Every real reply is scored live. Right or wrong. And we tell you which trap it fell into.
37. Flip on the answer key, and watch where the water really goes.
38. Or skip the models, and take the test yourself.

## The Product
39. And this isn't a one-off study. It's a benchmark anyone can use.
40. Every model gets a report card: skills, pairs, traps, and what happens without the image.
41. Got your own model? Download the pack, run it, drop the replies on the page. Same report card. Scored right in your browser.

## Findings
42. And here's the hopeful part. Train a small model on these scenes, and on scenes it has never seen, it climbs from ten to nineteen percent. Only with the image. It learns to look.
43. And people? They can take the very same test, online.

## Implementation · 25%
44. There's a Colab notebook, a pip-installable command, and automatic checks on every change.
45. And the frontier test runs on a free tier: one request per image, about three hundred tokens an answer.

## Impact · 15%
46. ThirstMap. A factory of visual tasks with verified answers, and a test AI can't bluff its way through.
47. Because before we trust AI with India's water, it should have to pass it.

