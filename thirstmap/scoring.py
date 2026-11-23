"""Parse a model's reply, score it against the reference answer, and diagnose wrong answers."""
import json
import re

COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
WORDS = {"NORTH": "N", "NORTHEAST": "NE", "NORTH-EAST": "NE", "EAST": "E", "SOUTHEAST": "SE",
         "SOUTH-EAST": "SE", "SOUTH": "S", "SOUTHWEST": "SW", "SOUTH-WEST": "SW", "WEST": "W",
         "NORTHWEST": "NW", "NORTH-WEST": "NW"}


def _extract_json(raw):
    raw = (raw or "").strip()
    try:
        return json.loads(raw), True
    except (ValueError, TypeError):
        pass
    for m in re.finditer(r"\{[^{}]*\}", raw, re.S):
        try:
            return json.loads(m.group(0)), True
        except ValueError:
            continue
    # cut-off or malformed JSON that still states its answer, e.g. '{"answer": "SW", "city": ...'
    m = re.search(r'"answer"\s*:\s*(\[[^\]]*\]|"[^"]*"|-?\d+(?:\.\d+)?|null)', raw)
    if m:
        try:
            return {"answer": json.loads(m.group(1))}, False
        except ValueError:
            pass
    return None, False


def _labels(value, options):
    """Normalise to a list of option labels (V3, S2, M1...)."""
    if value is None:
        return []
    if isinstance(value, str):
        if value.strip().lower() in ("none", "no", "", "[]"):
            return []
        value = re.split(r"[,\s;/]+(?:and\s+)?", value)
    out = []
    opts = {str(o).upper() for o in options}
    for v in value if isinstance(value, list) else [value]:
        t = str(v).strip().strip('"\'.').upper()
        if t in opts:
            out.append(t)
        else:
            found = [o for o in opts if re.search(rf"\b{re.escape(o)}\b", t)]
            out += found
    return sorted(set(out))


def well_formed(raw):
    """True if the reply states an answer in the requested form: a JSON object with "answer"
    (code fences allowed), or the whole reply is a plain JSON value such as ["V1", "V2"] or "SE"."""
    txt = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip()).strip()
    try:
        v = json.loads(txt)
        return not isinstance(v, dict) or "answer" in v
    except (ValueError, TypeError):
        obj, ok = _extract_json(raw)
        return ok and isinstance(obj, dict) and "answer" in obj


def parse(raw, task):
    obj, ok = _extract_json(raw)
    if isinstance(obj, dict) and "answer" in obj:
        value = obj["answer"]
    else:
        value, ok = raw, False                         # fall back to the free text
    sc = task["scoring"]
    if sc == "set":
        return _labels(value, task["options"]), ok
    if sc == "choice":
        got = _labels(value, task["options"])
        return (got[0] if len(got) == 1 else None), ok and len(got) == 1
    if sc == "compass":
        t = str(value).strip().strip('"\'.').upper().replace(" ", "")
        t = WORDS.get(t, t)
        return (t if t in COMPASS else None), ok and t in COMPASS
    if sc == "number":
        m = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return (float(m.group(0)) if m else None), ok and m is not None
    raise ValueError(sc)


def score(task, raw):
    pred, parse_ok = parse(raw, task)
    gold, sc = task["answer"], task["scoring"]
    if sc == "set":
        g, p = set(gold), set(pred)
        correct = g == p
        if not g and not p:
            credit = 1.0
        else:
            tp = len(g & p)
            prec = tp / len(p) if p else 0.0
            rec = tp / len(g) if g else 0.0
            credit = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    elif sc == "number":
        correct = pred is not None and abs(pred - gold) <= task["tolerance"]
        credit = float(correct)
    else:
        correct = pred == gold
        credit = float(correct)
    return dict(parsed=pred, parse_ok=parse_ok, correct=bool(correct), credit=round(credit, 4),
                tags=[] if correct else diagnose(task, pred, parse_ok))


def diagnose(task, pred, parse_ok):
    """Name the mistake. Trap tags come from the scene script, so they are exact."""
    if pred is None or pred == [] and task["scoring"] != "set":
        return ["unparseable_or_no_answer"] if not parse_ok else ["no_answer"]
    tags = []
    picked = set(pred) if isinstance(pred, list) else {pred}
    for kind, labels in (task.get("traps") or {}).items():
        if picked & set(labels):
            tags.append(f"trap:{kind}")
    sc, gold = task["scoring"], task["answer"]
    if sc == "set":
        if set(gold) - picked:
            tags.append("missed_some")
        if picked - set(gold) and not any(t.startswith("trap:") for t in tags):
            tags.append("extra_unrelated")
    elif sc == "compass":
        d = (COMPASS.index(pred) - COMPASS.index(gold)) % 8
        tags.append("reversed_direction" if d == 4 else "off_by_one_sector" if d in (1, 7) else "wrong_direction")
    elif sc == "number":
        tags.append("overestimate" if pred > gold else "underestimate")
    elif not tags:
        tags.append("wrong_choice")
    return tags


def chance(task):
    """Probability that the random baseline (mock:random) answers this task correctly.

    choice/compass: 1/number of options; set: each option picked independently with p=0.35;
    number: uniform over the option range, within the tolerance.
    """
    sc, opts, gold = task["scoring"], task["options"], task["answer"]
    if sc in ("choice", "compass"):
        return 1 / len(opts)
    if sc == "set":
        k, n = len(gold), len(opts)
        return 0.35 ** k * 0.65 ** (n - k)
    lo, hi = opts
    return (min(gold + task["tolerance"], hi) - max(gold - task["tolerance"], lo)) / (hi - lo)
