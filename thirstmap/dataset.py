"""Turn validated scenes into evaluation tasks (one per question x image style).

Each task carries everything needed to ask a model and score its answer
automatically: image path, prompt, answer, scoring rule, answer options.
"""

ANSWER_FORMAT = {
    "set": 'a JSON list of labels, e.g. ["V1", "V4"], or [] if none',
    "choice": 'a single label as a JSON string, e.g. "B"',
    "compass": 'one of "N", "NE", "E", "SE", "S", "SW", "W", "NW" as a JSON string',
    "number": "a single number",
}
SCORING = {"Q1": "set", "Q2": "choice", "Q3": "choice", "Q4": "set", "Q5": "compass",
           "Q6": "choice", "Q7": "set", "Q8": "set", "Q9": "number",
           "Q10": "number"}

STYLE_INTRO = {
    "satellite": "This is an annotated satellite-style image of a 4 km x 4 km area. "
                 "{drain} North is up.",
    "map": "This is a topographic map of a 4 km x 4 km area with contour lines (elevation), "
           "streams and lakes. North is up.",
    "thermal": "This is a thermal image of a 4 km x 4 km area. Land is grey; streams and lakes are "
               "coloured by how much warmer than normal the water is (see the colour bar). North is up.",
}


def prompt_for(question, style, scoring, drain="Streams drain off the southern edge."):
    return (f"{STYLE_INTRO[style].format(drain=drain)}\n\nQuestion: {question}\n\n"
            "Look carefully at the image. Reply with ONLY a JSON object of the form "
            f'{{"answer": ...}} where the answer is {ANSWER_FORMAT[scoring]}.')


def tasks_for_scene(scene_id, level, questions, image_paths, reveal_paths, drain=None, terrain="synthetic"):
    tasks = []
    for q in questions:
        scoring = SCORING[q["id"]]
        for style in q["styles"]:
            tasks.append(dict(
                task_id=f"{scene_id}__{q['id']}__{style}",
                scene_id=scene_id, level=level, qid=q["id"], skill=q["skill"], style=style,
                image=image_paths[style], reveal=reveal_paths[style],
                question=q["question"], terrain=terrain,
                prompt=prompt_for(q["question"], style, scoring, drain or "Streams drain off the southern edge."),
                scoring=scoring, answer=q["answer"],
                tolerance=q.get("tolerance"), options=q.get("options"), traps=q.get("traps", {}),
            ))
    return tasks
