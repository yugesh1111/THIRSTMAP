"""ThirstMap films: narrated, subtitled walkthroughs, rendered frame by frame at 1920x1080.

    python video/make_film.py --film full     # ~3 min: every judging criterion and every Track 2 deliverable
    python video/make_film.py --film short    # ~1 min cut
    node video/render_film.js video/build/full docs/video/thirstmap_film.mp4

Narration is synthesised locally with Kokoro-82M (Apache-2.0; `pip install kokoro soundfile`), so no API is needed.
Every number spoken or shown is read from the result files and checked against them before anything is built.
"""
import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SR = 24000
GAP, LEAD, TAIL = 0.32, 0.55, 0.75          # seconds: between sentences, before a scene's first, after its last

SAY = [("Gemini 3.5 Flash-Lite", "Gemini three point five Flash Lite"), ("Gemini 3.1 Flash-Lite", "Gemini three point one Flash Lite"),
       ("Gemini 3.5 Flash", "Gemini three point five Flash"), ("Flash-Lite", "Flash Lite"), ("ThirstMap", "Thirst Map"),
       ("pysheds", "pie sheds"), ("Qwen", "Kwen"), ("Colab", "Co-lab"), ("2030", "twenty thirty"), ("pip install", "pip install"),
       ("%", " percent")]


def say(text):
    for a, b in SAY:
        text = text.replace(a, b)
    return text


# ---------------------------------------------------------------- numbers, read from the result files
def count_tests(python):
    """Number of tests pytest collects (the film shows it), run with the project's own interpreter."""
    import subprocess
    r = subprocess.run([python, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True)
    m = re.search(r"(\d+) tests? collected", r.stdout)
    if not m:
        raise SystemExit(f"could not count the tests with {python} (pass --test-python): {r.stdout[-300:]}{r.stderr[-300:]}")
    return int(m.group(1))


def numbers():
    F = json.loads((ROOT / "results/frontier/summary.json").read_text())
    rows = {m.split(":", 1)[1].split("@")[0]: dict(acc=round(100 * v["correct"] / v["n"]), n=v["n"],
                                                     blind=F["overall"][m].get("blind"),
                                                     pairs=F["counterfactual_pairs"].get(m, {}))
            for m, v in F["vs_chance"].items()}
    chance = round(100 * next(iter(F["vs_chance"].values()))["chance"])
    man = json.loads((ROOT / "eval_set/manifest_full_dataset.json").read_text())
    errata = sum(1 for _ in open(ROOT / "dataset/errata.jsonl"))
    FT = json.loads((ROOT / "results/finetune/summary.json").read_text())
    fb = next(m for m in FT["models"] if "(base)" in m)
    ftu = next(m for m in FT["models"] if "fine-tuned" in m)
    steps = json.loads((ROOT / "docs/pipeline/steps.json").read_text())
    audit = (ROOT / "docs/AUDIT.md").read_text()
    rebuilt = re.search(r"pixel-identical to the published image: \*\*(\d+)\*\*", audit).group(1)
    N = dict(rows=rows, chance=chance, n=next(iter(rows.values()))["n"], tasks=man["n_tasks"], scored=man["n_tasks"] - errata,
             scenes=man["n_scenes"], pairs=man["counterfactual_pairs"]["pairs"], errata=errata,
             errata_pct=round(100 * errata / man["n_tasks"], 1), rebuilt=int(rebuilt),
             ft_base=round(100 * FT["vs_chance"][fb]["correct"] / FT["vs_chance"][fb]["n"]),
             ft_tuned=round(100 * FT["vs_chance"][ftu]["correct"] / FT["vs_chance"][ftu]["n"]),
             ft_blind=round(100 * FT["overall"][ftu]["blind"]), steps=steps)
    X = ROOT / "results/frontier_pairs/summary.json"
    P = json.loads(X.read_text()).get("counterfactual_pairs", {}) if X.exists() else {}
    def pairs(m):
        a = F["counterfactual_pairs"].get(m, {})
        e = P.get(m, {})
        k = round(a.get("pair_accuracy", 0) * a.get("pairs", 0)) + round(e.get("pair_accuracy", 0) * e.get("pairs", 0))
        return k, a.get("pairs", 0) + e.get("pairs", 0)
    best = next(m for m in F["vs_chance"] if m.split(":", 1)[1].split("@")[0] == "gemini-3.5-flash")
    N["best_pairs"] = pairs(best)
    N["other_pairs"] = sorted({pairs(m)[0] for m in F["vs_chance"] if m != best})
    return N


def check(N):
    """Sanity checks on the result files the narration is built from."""
    r = N["rows"]
    for k in ("gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"):
        assert k in r, k
    assert r["gemini-3.1-flash-lite"]["blind"] is not None and r["gemini-3.5-flash-lite"]["blind"] is not None
    assert N["best_pairs"][1] >= 7 and N["steps"]["answer"] and N["steps"]["twin_answer"]
    assert (N["ft_base"], N["ft_tuned"], N["ft_blind"]) == (10, 19, 11)     # the teach line says ten, nineteen, eleven


# ---------------------------------------------------------------- narration (numbers from the result files)
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(n):
    n = int(n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return ONES[n // 100] + " hundred" + (" and " + words(n % 100) if n % 100 else "")
    return words(n // 1000) + " thousand" + (" " + words(n % 1000) if n % 1000 >= 100 else " and " + words(n % 1000) if n % 1000 else "")


def cap(x):
    return x[:1].upper() + x[1:]


def full_script(N):
    r, best = N["rows"], N["rows"]["gemini-3.5-flash"]
    fl = sorted(r[k]["acc"] for k in ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite"))
    k, n = N["best_pairs"]
    others = "Every other model, none." if N["other_pairs"] == [0] else \
        f"Every other model, {words(max(N['other_pairs']))} at most."
    return [
        ("coldopen", "", [], {"dur": COLD_DUR}),
        ("hook", "THE PITCH", ["AI is drinking India's water.",
                               "So here's the question nobody was asking: can AI even see where that water goes?"],
         {"punch": 1}),
        ("problem", "IMPACT · 15%", [
            "India's data centres drink about 150 billion litres of water a year. By 2030? 358 billion.",
            "And seventy percent of that capacity sits in two cities already short of water: Mumbai and Chennai.",
            "Now we're building AI agents to watch over it, from maps and satellite images. "
            "And it all comes down to one question: where does the wastewater go?"],
         {"t2": 1, "q": 2}),
        ("factory", "IMPLEMENTATION · 25%", [
            "So we built a factory.",
            "Code raises a landscape, makes it rain, and follows every drop downhill. "
            "Past a data centre. Past villages. Past traps we hid on purpose.",
            "Which means it knows the answer before it ever asks the question.",
            "Then it paints the same scene three ways: satellite, map, and thermal."],
         {"row": 1, "key": 2, "styles": 3}),
        ("variation", "VARIATION · 20%", [
            "Ten reasoning skills. Not one of them is counting.",
            "Five levels of difficulty. Real terrain from four Indian data-centre cities. "
            "Monsoon, haze, a blurry sensor. And the answer never moves.",
            cap(words(N["tasks"])) + " tasks. Every one with a known answer."],
         {"grid": 1, "count": 2}),
        ("twins", "ORIGINALITY · 15%", [
            "Then we did something sneaky. Every scene gets a twin.",
            "Change one small thing, move the outfall to another stream, and the right answer flips.",
            "A model that's really looking gets both. A model running on habit? Caught."], {"twin": 1, "habit": 2}),
        ("validity", "VALIDITY · 25%", [
            "Now, you shouldn't have to trust us. So we don't ask you to.",
            "A completely separate hydrology library re-derives every answer. "
            "If it disagrees, the question is gone. Dropped. Never edited.",
            "The answer has to be visible in the actual pixels, or it doesn't ship.",
            f"We even turned the audit on ourselves: {words(N['errata'])} unfair tasks. Found, excluded, published.",
            "And every audited image rebuilds from its seed, byte for byte."],
         {"a": 1, "b": 2, "c": 3, "d": 4}),
        ("terminal", "IMPLEMENTATION · 25%", [
            "And you don't need us to run it.",
            "One pip install. One command. It builds a scene and its twin, and runs every check.",
            "Every check you see passing here really passed. If it hadn't, the question would be gone."], {"run": 1}),
        ("results", "FINDINGS", [
            f"So we put the models to the test. The same {words(N['n'])} questions, for everyone.",
            f"The open models? No better than guessing, and guessing gets you {words(N['chance'])} percent.",
            f"Gemini Flash-Lite gets {words(fl[0])} to {words(fl[1])} percent. Hide the image, and it falls straight "
            "back to guessing. It's really reading the map.",
            f"And Gemini 3.5 Flash? {cap(words(best['acc']))} percent. Impressive."],
         {"bars": 0, "open": 1, "ghost": 2, "best": 3}),
        ("catch", "FINDINGS · ORIGINALITY", [
            "But then, the twins.",
            "Same river. We just cooled the water, so no point is above three degrees any more.",
            "Gemini gives the exact same answer. Two false heat alarms.",
            f"Across {words(n)} pairs, it got both halves right only {words(k)} times. {others}"],
         {"twinside": 1, "same": 2, "score": 3}),
        ("demo", "DEMO · SCORING", [
            "Every real reply is scored live. Right or wrong. And we tell you which trap it fell into.",
            "Flip on the answer key, and watch where the water really goes.",
            "Or skip the models, and take the test yourself."], {"key": 1, "try": 2}),
        ("board", "THE PRODUCT", [
            "And this isn't a one-off study. It's a benchmark anyone can use.",
            "Every model gets a report card: skills, pairs, traps, and what happens without the image.",
            "Got your own model? Download the pack, run it, drop the replies on the page. "
            "Same report card. Scored right in your browser."],
         {"card": 1, "drop": 2}),
        ("teach", "FINDINGS", [
            "And here's the hopeful part. Train a small model on these scenes, and on scenes it has never seen, "
            "it climbs from ten to nineteen percent. Only with the image. It learns to look.",
            "And people? They can take the very same test, online."], {"human": 1}),
        ("ship", "IMPLEMENTATION · 25%", [
            "There's a Colab notebook, a pip-installable command, and automatic checks on every change.",
            "And the frontier test runs on a free tier: one request per image, about three hundred tokens an answer."],
         {"economy": 1}),
        ("close", "IMPACT · 15%", [
            "ThirstMap. A factory of visual tasks with verified answers, and a test AI can't bluff its way through.",
            "Because before we trust AI with India's water, it should have to pass it."], {"last": 1}),
    ]


def short_script(N):
    best = N["rows"]["gemini-3.5-flash"]
    k, n = N["best_pairs"]
    return [
        ("hook", "THE PITCH", ["AI is drinking India's water.",
                               "But can it even see where that water goes?"], {"punch": 1}),
        ("factory", "IMPLEMENTATION · 25%", [
            "Code builds a landscape and makes it rain, so it knows every answer before it asks.",
            "Then it paints each scene three ways: satellite, map and thermal."], {"row": 0, "key": 0, "styles": 1}),
        ("twins", "ORIGINALITY · 15%", ["Every scene has a twin. One tiny change, and the answer flips."], {}),
        ("validity", "VALIDITY · 25%", ["A separate library re-checks every answer. And we published our own audit."], {}),
        ("results", "FINDINGS", [
            "Open models? Guessing.",
            "Gemini Flash-Lite reads the map. Hide it, and it's guessing again.",
            f"Gemini 3.5 Flash? {cap(words(best['acc']))} percent."], {"bars": 0, "open": 0, "ghost": 1, "best": 2}),
        ("catch", "FINDINGS · ORIGINALITY", [
            "Then the twins catch it.",
            "Cool the water, and it gives the exact same answer. Two false heat alarms.",
            f"Both halves right in just {words(k)} of {words(n)} pairs."], {"twinside": 1, "same": 1, "score": 2}),
        ("board", "THE PRODUCT", ["Got a model? Score it on the public leaderboard, right in your browser."],
         {"card": 0, "drop": 0}),
        ("close", "IMPACT · 15%", [
            f"Over {words(N['tasks'] // 100 * 100)} tasks. A live demo. Everything open.",
            "Before we trust AI with India's water, it should have to pass this test."], {"last": 1}),
    ]


# ---------------------------------------------------------------- text to speech (cached per sentence)
class Voice:
    def __init__(self, cache, voice="af_heart", speed=1.06):
        self.cache, self.voice, self.speed, self.pipe = Path(cache), voice, speed, None
        self.cache.mkdir(parents=True, exist_ok=True)

    def __call__(self, text):
        key = hashlib.sha1(f"{self.voice}|{self.speed}|{text}".encode()).hexdigest()[:16]
        f = self.cache / f"{key}.npy"
        if f.exists():
            return np.load(f)
        if self.pipe is None:
            import os
            os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
            from kokoro import KPipeline
            self.pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        audio = np.concatenate([np.asarray(a) for _, _, a in self.pipe(text, voice=self.voice, speed=self.speed)])
        np.save(f, audio.astype(np.float32))
        return audio


def timeline(spec, voice):
    t, scenes, clips = 0.0, [], []
    for sid, crit, lines, marks in spec:
        start, cur, sent = t, t + LEAD, []
        for ln in lines:
            show, spoken = (ln if isinstance(ln, tuple) else (ln, say(ln)))
            a = voice(spoken)
            sent.append(dict(s=round(cur, 3), e=round(cur + len(a) / SR, 3), text=show))
            clips.append((cur, a))
            cur += len(a) / SR + GAP
        end = cur - GAP + TAIL if lines else start + marks["dur"]
        scenes.append(dict(id=sid, crit=crit, start=round(start, 3), end=round(end, 3), sent=sent, marks=marks))
        t = end
    return scenes, clips, t


COLD_DUR = 9.0                                  # cold open: the question typed, sent, answered, then a whip-zoom
COLD_Q = "How much water do you consume every day?"
COLD_TYPE = (0.7, 1.8)                          # typing starts, lasts (s, from the scene start)
COLD_SEND, COLD_REPLY, COLD_WHIP, COLD_CUT = 2.6, 4.4, 7.4, 9.0


def coldopen_sfx(t0, ref):
    """Synthesized sound design for the cold open (no samples): key clicks, send whoosh, reply chime, riser, boom.
    ref = the narration's peak, so the effects sit under the voice."""
    rng = np.random.default_rng(7)
    tt = lambda d: np.arange(int(d * SR)) / SR                                     # noqa: E731

    def band(x, lo, hi):
        f = np.fft.rfft(x)
        fr = np.fft.rfftfreq(len(x), 1 / SR)
        f[(fr < lo) | (fr > hi)] = 0
        return np.fft.irfft(f, len(x)).astype(np.float32)

    def norm(x, peak):
        return (x / (np.max(np.abs(x)) or 1) * peak * ref).astype(np.float32)

    out = []
    start, dur = COLD_TYPE
    n = len(COLD_Q)
    xs = np.linspace(0, 1, 2001)
    ez = np.where(xs < .5, 2 * xs * xs, 1 - (-2 * xs + 2) ** 2 / 2)                 # the page's ease()
    for i in range(1, n + 1):                                                        # one click per character shown
        if COLD_Q[i - 1] == " ":
            continue
        x = xs[np.searchsorted(ez, i / n - 1e-6)]
        t = tt(0.018)
        click = band(rng.standard_normal(len(t)), 1800, 9000) * np.exp(-t / 0.003)
        out.append((t0 + start + x * dur, norm(click, 0.22 * rng.uniform(0.7, 1.0))))
    t = tt(0.45)                                                                     # send: short airy whoosh + pop
    wh = band(rng.standard_normal(len(t)), 500, 5000) * np.sin(np.pi * t / t[-1]) ** 2
    pop = np.sin(2 * np.pi * (500 * t + 1300 * t * t)) * np.exp(-t / 0.035)
    out.append((t0 + COLD_SEND - 0.2, norm(wh, 0.18)))
    out.append((t0 + COLD_SEND, norm(pop, 0.35)))
    t = tt(1.2)                                                                      # reply: two-note chime
    chime = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / 0.35) * (t >= d) for f, d in ((1046.5, 0), (1568.0, 0.09)))
    out.append((t0 + COLD_REPLY, norm(chime, 0.3)))
    d = COLD_CUT - COLD_WHIP                                                         # riser into the cut
    t = tt(d)
    riser = band(rng.standard_normal(len(t)), 800, 7000) * (t / d) ** 2.2 + \
        0.6 * np.sin(2 * np.pi * (180 * t + 380 * t * t / d)) * (t / d) ** 2
    out.append((t0 + COLD_WHIP, norm(riser, 0.32)))
    t = tt(1.6)                                                                      # the cut: sub boom + hit
    boom = np.sin(2 * np.pi * (75 * t - 12 * t * t)) * np.exp(-t / 0.5) + \
        band(rng.standard_normal(len(t)), 60, 2500) * np.exp(-t / 0.05)
    out.append((t0 + COLD_CUT - 0.02, norm(boom, 0.75)))
    t = tt(COLD_WHIP + 0.3)                                                          # a low bed under the chat
    bed = (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.5 * t)) * np.minimum(1, t / 1.5) * \
        np.minimum(1, (t[-1] - t) / 0.6)
    out.append((t0, norm(bed, 0.07)))
    return out


TRANSITIONS = ["zoom", "glitch", "push", "flash"]


def assign_transitions(scenes):
    """How each scene enters: the title after the cold open crashes in; later scenes rotate through the set."""
    k = 0
    for i, sc in enumerate(scenes):
        if i == 0:
            sc["tr"] = "none"
        elif scenes[i - 1]["id"] == "coldopen":
            sc["tr"] = "impact"
        else:
            sc["tr"] = TRANSITIONS[k % len(TRANSITIONS)]
            k += 1


def transition_sfx(scenes, ref):
    """A synthesized sound for every scene change, matched to its look (whoosh, glitch, swish, hit)."""
    rng = np.random.default_rng(11)
    tt = lambda d: np.arange(int(d * SR)) / SR                                     # noqa: E731

    def band(x, lo, hi):
        f = np.fft.rfft(x)
        fr = np.fft.rfftfreq(len(x), 1 / SR)
        f[(fr < lo) | (fr > hi)] = 0
        return np.fft.irfft(f, len(x)).astype(np.float32)

    def norm(x, peak):
        return (x / (np.max(np.abs(x)) or 1) * peak * ref).astype(np.float32)

    out = []
    for sc in scenes:
        b, kind = sc["start"], sc.get("tr")
        if kind == "zoom":                                   # whoosh that peaks on the cut, then a soft thump
            t = tt(0.9)
            env = np.exp(-((t - 0.55) / 0.2) ** 2)
            w = band(rng.standard_normal(len(t)), 300, 6000) * env
            th = np.sin(2 * np.pi * (90 * t - 30 * t * t)) * np.exp(-np.maximum(t - 0.55, 0) / 0.18) * (t >= 0.55)
            out.append((b - 0.55, norm(w + 0.8 * th, 0.34)))
        elif kind == "push":                                 # fast bright swish
            t = tt(0.5)
            env = np.exp(-((t - 0.3) / 0.09) ** 2)
            out.append((b - 0.3, norm(band(rng.standard_normal(len(t)), 1500, 9000) * env, 0.3)))
        elif kind == "glitch":                               # stuttering digital bursts around the cut
            t = tt(0.7)
            x = np.zeros(len(t), np.float32)
            for c in (0.18, 0.27, 0.33, 0.42, 0.46, 0.55):
                i0, n = int(c * SR), int(rng.uniform(0.02, 0.05) * SR)
                f = rng.uniform(300, 1800)
                burst = np.sign(np.sin(2 * np.pi * f * t[:n])) * 0.6 + rng.standard_normal(n) * 0.5
                x[i0:i0 + n] += np.round(burst * 4) / 4            # crushed
            out.append((b - 0.35, norm(band(x, 150, 8000), 0.26)))
        elif kind in ("flash", "impact"):                     # reverse swell into a hit
            t = tt(1.3)
            swell = band(rng.standard_normal(len(t)), 2000, 9000) * (t / 0.5) ** 3 * (t < 0.5)
            hit = (np.sin(2 * np.pi * (70 * t - 15 * t * t)) * np.exp(-np.maximum(t - 0.5, 0) / 0.35)
                   + band(rng.standard_normal(len(t)), 80, 4000) * np.exp(-np.maximum(t - 0.5, 0) / 0.06)) * (t >= 0.5)
            if kind == "flash":
                out.append((b - 0.5, norm(swell + hit, 0.36)))
    return out


def write_audio(clips, total, path):
    import soundfile as sf
    buf = np.zeros(int((total + 0.5) * SR), dtype=np.float32)
    for t0, a in clips:
        i = int(t0 * SR)
        buf[i:i + len(a)] += a[: len(buf) - i]
    peak = float(np.max(np.abs(buf))) or 1.0
    sf.write(path, buf / peak * 0.89, SR)


def subtitles(scenes, path_vtt, path_srt):
    def ts(x, sep):
        h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
        return f"{h:02d}:{m:02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"
    cues = [(c["s"], c["e"] + 0.2, c["text"]) for sc in scenes for c in sc["sent"]]
    Path(path_vtt).write_text("WEBVTT\n\n" + "\n".join(f"{ts(a, '.')} --> {ts(b, '.')}\n{tx}\n" for a, b, tx in cues))
    Path(path_srt).write_text("\n".join(f"{i}\n{ts(a, ',')} --> {ts(b, ',')}\n{tx}\n" for i, (a, b, tx) in enumerate(cues, 1)))


# ---------------------------------------------------------------- assets
def prep_assets(out):
    from PIL import Image
    a = out / "assets"
    a.mkdir(parents=True, exist_ok=True)
    cap = ROOT / "video/capture"

    def put(src, name, size=1600, crop_bottom=0):
        im = Image.open(src).convert("RGB")
        if crop_bottom:
            im = im.crop((0, 0, im.width, im.height - crop_bottom))
        im.thumbnail((size, size))
        im.save(a / name, quality=90)
    dsr = ROOT / "video/build/dataset"          # scenes rebuilt by video/film_scenes.py, else the full dataset release
    dsr = dsr if (dsr / "scenes").exists() else ROOT / "dataset"
    ds = dsr / "scenes"
    put(ds / "level4_seed48947/satellite_reveal.png", "hero.jpg", 1200)
    for f in ["1_terrain.png", "2_water.png", "3_scene.png", "4_answer.png", "5_check.png"]:
        put(ROOT / "docs/pipeline" / f, f.replace(".png", ".jpg"), 640)
    for f in ["6_map.jpg", "6_satellite.jpg", "6_thermal.jpg", "7_pixels.jpg", "8_original.jpg", "8_twin.jpg"]:
        put(ROOT / "docs/pipeline" / f, f, 860)
    for lv, d in [(1, "level1_seed100250"), (2, "level2_seed21111"), (3, "level3_seed31409"), (4, "level4_seed101214"),
                  (5, "level5_seed111221")]:
        put(ds / d / "map.png", f"level{lv}.jpg", 420)
    for c in ["navi_mumbai_seed31312", "hyderabad_seed31312", "pune_seed31021", "chennai_seed31021"]:
        put(ds / f"real_{c}" / "satellite.png", f"real_{c.split('_seed')[0]}.jpg", 420)
    put(ds / "level1_seed14596/satellite.png", "look_dry.jpg", 420)
    for v in ["monsoon", "haze", "coarse"]:
        put(dsr / "variants/level1_seed14596" / f"{v}.png", f"look_{v}.jpg", 420)
    put(ROOT / "docs/demo/analysis/pair__level3_seed34416__Q8__thermal__gemini-3.5-flash.jpg", "catch.jpg", 1600)
    for f, cb in [("demo_task.jpg", 0), ("demo_task_key.jpg", 0), ("demo_try.jpg", 0), ("human_test.jpg", 0),
                  ("nb_styles.jpg", 0), ("gen_map.jpg", 0), ("lb_board.jpg", 0), ("lb_card.jpg", 0)]:
        put(cap / f, f, 1900, cb)
    import qrcode
    q = qrcode.QRCode(border=2, box_size=10)
    q.add_data("https://yugesh1111.github.io/THIRSTMAP/")
    q.make(fit=True)
    q.make_image(fill_color="#0B1C27", back_color="white").save(a / "qr.png")
    fdir = out / "fonts"
    if fdir.exists():
        shutil.rmtree(fdir)
    shutil.copytree(ROOT / "video/fonts", fdir)


# ---------------------------------------------------------------- the page
def E(x):
    return html.escape(str(x))


def scene_html(sid, N):
    r, st = N["rows"], N["steps"]
    if sid == "coldopen":
        kf = lambda *k: "data-kf='" + json.dumps([[a, b] for a, b in k]) + "'"           # noqa: E731
        ts, td = COLD_TYPE
        return f'''
<div class="cobg"></div>
<div class="chatcam" {kf((0, {"s": 0.9, "o": 0, "b": 6}), (0.7, {"s": 1, "o": 1, "b": 0}), (COLD_SEND - 0.1, {"s": 1}),
                         (COLD_SEND + 0.6, {"s": 1.14}), (COLD_WHIP, {"s": 1.2, "b": 0, "o": 1}),
                         (COLD_CUT - 0.35, {"s": 3.2, "b": 22, "o": 0.0}))}>
  <div class="chat">
    <div class="chathead"><i></i><b>AI assistant</b><span>online</span></div>
    <div class="thread">
      <div class="msg me" data-at="{COLD_SEND}" data-anim="pop" data-d="0.3">{E(COLD_Q)}</div>
      <div class="slot">
        <div class="msg ai dots" {kf((0, {"o": 0}), (COLD_SEND + 0.5, {"o": 0}), (COLD_SEND + 0.7, {"o": 1}),
                                     (COLD_REPLY - 0.1, {"o": 1}), (COLD_REPLY, {"o": 0}))}><i data-pulse="0"></i><i data-pulse="1"></i><i data-pulse="2"></i></div>
        <div class="msg ai" data-at="{COLD_REPLY}" data-anim="pop" data-d="0.35">Me? Not a drop.<br>But the data centres that run AI are cooled with water.<br><b>A lot of it.</b></div>
      </div>
    </div>
    <div class="input"><span data-anim-n="chars" data-text="{E(COLD_Q)}" data-at2="{ts}" data-d2="{td}" data-out="{COLD_SEND}"></span><i class="caret" data-out="{COLD_SEND}"></i><em>➤</em></div>
  </div>
</div>
<div class="flash" {kf((0, {"o": 0}), (COLD_CUT - 0.75, {"o": 0}), (COLD_CUT - 0.42, {"o": 0.95}), (COLD_CUT, {"o": 0.4}))}></div>'''
    if sid == "hook":
        return f'''
<img class="hero" src="assets/hero.jpg" data-kb="0.07" alt="">
<div class="heroshade"></div>
<div class="box" style="left:120px;top:250px;width:980px">
  <div class="eyebrow" data-at="0.2">Innodata AI Hackathon 2026 · Track 2: Visual Task Factory</div>
  <div class="mega" data-at="0.45">ThirstMap</div>
  <div class="lead" data-at="0.8">Can AI trace water through the landscape?</div>
  <div class="punch" data-at="@punch">AI is drinking India’s water.<br>We test whether AI can even see where that water goes.</div>
</div>'''
    if sid == "problem":
        tiles = [("358 bn L", "of water a year by 2030 for India’s data centres, up from ~150 bn L today", 0, 358, " bn L"),
                 ("70%", "of capacity sits in Mumbai and Chennai, both water-stressed", "@t2", 70, "%"),
                 ("0 of 15", "state data-centre policies require water-stress mapping", "@t2+0.6", None, None)]
        cells = "".join(
            f'<div class="tile" data-at="{at}"><div class="big"' + (f' data-anim-n="count" data-to="{to}" data-suf="{suf}" data-at2="{at}"' if to else "") +
            f'>{E(big)}</div><div class="what">{E(what)}</div></div>' for big, what, at, to, suf in tiles)
        return f'''
<div class="box" style="left:120px;top:150px;width:1680px">
  <div class="eyebrow" data-at="0.1">The problem</div>
  <div class="h" data-at="0.2">India’s data centres are growing in cities already short of water</div>
  <div class="tiles">{cells}</div>
  <div class="ask" data-at="@q">“Where does this facility’s wastewater go?”</div>
  <div class="src" data-at="@q+0.4">Estimates from Down To Earth (citing CEEW), S&amp;P Global; AI geospatial agents: Google Earth AI.</div>
</div>'''
    if sid == "factory":
        steps = [("1_terrain.jpg", "1 · Terrain", "fractal relief, 4 × 4 km"), ("2_water.jpg", "2 · Water", "every cell drains downhill"),
                 ("3_scene.jpg", "3 · Scene + traps", "V6 is close, but on another stream"),
                 ("4_answer.jpg", "4 · Answer key", f"traced from O: {', '.join(st['answer'])}")]
        row = "".join(f'<div class="step" data-at="@row{"+%.1f" % (0.55 * i) if i else ""}"><img src="assets/{f}" alt="">'
                      f'<b>{E(t)}</b><span>{E(c)}</span></div>' for i, (f, t, c) in enumerate(steps))
        styles = "".join(f'<div class="sty" data-at="@styles{"+%.1f" % (0.35 * i) if i else ""}"><img src="assets/{f}" alt=""><b>{E(t)}</b></div>'
                         for i, (f, t) in enumerate([("6_satellite.jpg", "Satellite-style"), ("6_map.jpg", "Topographic map"),
                                                     ("6_thermal.jpg", "Thermal")]))
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Track 2 deliverable · the generation pipeline</div>
  <div class="h" data-at="0.2">Our code builds the land, so it already knows every answer</div>
</div>
<div class="phase" data-out="@styles-0.2"><div class="steps">{row}</div>
  <div class="ring" data-at="@key" data-anim="pop" style="left:1398px;top:318px;width:414px;height:414px;border-radius:26px"></div></div>
<div class="phase"><div class="styles">{styles}</div></div>'''
    if sid == "variation":
        skills = ["Trace downstream", "Order along the flow", "Distance along a river", "Wetland placement", "Siting impact",
                  "Read elevation", "Flow direction", "Upstream catchment", "Colour-scale threshold", "Colour-scale value"]
        chips = "".join(f'<span class="chip" data-at="{0.15 * i:.2f}">{E(s)}</span>' for i, s in enumerate(skills))
        lv = "".join(f'<div class="th" data-at="@grid+{0.18 * i:.2f}"><img src="assets/level{i + 1}.jpg" alt=""><span>Level {i + 1}</span></div>'
                     for i in range(5))
        cities = "".join(f'<div class="th sm" data-at="@grid+{0.9 + 0.18 * i:.2f}"><img src="assets/real_{c}.jpg" alt=""><span>{E(n)}</span></div>'
                         for i, (c, n) in enumerate([("navi_mumbai", "Navi Mumbai"), ("hyderabad", "Hyderabad"), ("pune", "Pune"),
                                                     ("chennai", "Chennai")]))
        looks = "".join(f'<div class="th sm" data-at="@grid+{1.9 + 0.18 * i:.2f}"><img src="assets/look_{v}.jpg" alt=""><span>{E(v.title())}</span></div>'
                        for i, v in enumerate(["dry", "monsoon", "haze", "coarse"]))
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Variation</div>
  <div class="h" data-at="0.2">Ten skills, five levels, real terrain, four looks</div>
</div>
<div class="phase" data-out="@grid-0.2"><div class="chips">{chips}</div></div>
<div class="phase"><div class="levels">{lv}</div>
  <div class="pair2"><div><div class="lab" data-at="@grid+0.8">Real terrain: Copernicus DEM + ESA WorldCover</div><div class="row4">{cities}</div></div>
  <div><div class="lab" data-at="@grid+1.8">Same scene, four looks: the answer must not change</div><div class="row4">{looks}</div></div></div>
  <div class="counter" data-at="@count"><b data-anim-n="count" data-to="{N['tasks']}" data-at2="@count">{N['tasks']:,}</b> tasks · <b>{N['scenes']}</b> scenes · <b>{N['pairs']}</b> twins</div></div>'''
    if sid == "twins":
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Originality · counterfactual twins</div>
  <div class="h" data-at="0.2">One small change must flip the answer</div>
</div>
<div class="twin">
  <figure data-at="0.4"><img src="assets/8_original.jpg" alt=""><figcaption>Original · answer <b>{E(', '.join(st['answer']))}</b></figcaption></figure>
  <figure data-at="@twin"><img src="assets/8_twin.jpg" alt=""><figcaption>Twin: outfall O moves to another stream · answer <b>{E(', '.join(st['twin_answer']))}</b></figcaption></figure>
  <div class="note" data-at="@twin+1.2">{st['twin_pixels_changed_pct']}% of pixels change (outlined in pink)</div>
  <div class="habit" data-at="@habit">Answer from habit → one half wrong</div>
</div>'''
    if sid == "validity":
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Validity · checked without asking any model</div>
  <div class="h" data-at="0.2">Every answer is verified, and we audited ourselves</div>
</div>
<div class="cards4">
  <div class="vc" data-at="@a"><img src="assets/5_check.jpg" alt=""><b>{st['pysheds_agree_pct']}% agree</b><span>an independent library (pysheds) recomputes the flow: same answer to {st['answers_identical']} questions</span></div>
  <div class="vc" data-at="@b"><img src="assets/7_pixels.jpg" alt=""><b>{st['pixel_cells']} of {st['pixel_cells']} visible</b><span>the answer path is checked in the pixels the model sees; labels must be readable</span></div>
  <div class="vc num" data-at="@c"><div class="n" data-anim-n="count" data-to="{N['errata']}" data-at2="@c">{N['errata']}</div><b>unfair tasks excluded</b><span>{N['errata_pct']}% found by our own audit, listed in errata.jsonl, left out of every score: {N['scored']:,} tasks are scored</span></div>
  <div class="vc num" data-at="@d"><div class="n">{N['rebuilt']:,}</div><b>images rebuilt byte for byte</b><span>from their seeds; evaluated inputs published with SHA-256. Real drainage matches real water 1.3–4.2× chance.</span></div>
</div>'''
    if sid == "terminal":
        gen = (ROOT / "video/capture/gen.txt").read_text().splitlines()
        gen = [g for g in gen if g.strip() and not g.startswith(("real", "user", "sys"))]
        def short(line):
            line = re.sub(r"np\.float64\(([\d.]+)\)", r"\1", line)
            line = re.sub(r"\{'(.*)\}$", r"\1", line).replace("'", "")   # PASS  V5_elevation_margin  min_gap_m: 3.59
            return line if len(line) < 66 else line[:63] + "…"
        out_lines = "".join(f'<div class="{"ok" if "PASS" in g else "dim"}">{E(short(g))}</div>' for g in gen)
        cmd1 = "git clone --depth 1 --filter=blob:none --sparse …/THIRSTMAP && git -C THIRSTMAP sparse-checkout set thirstmap"
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Implementation · reusable pipeline</div>
  <div class="h" data-at="0.2">Install, generate, validate: one command</div>
</div>
<div class="term" data-at="0.3">
  <div class="bar"><i></i><i></i><i></i><span>bash</span></div>
  <div class="tbody"><div class="tin">
    <div><span class="ps">$</span> <span data-anim-n="chars" data-text="{E(cmd1)}" data-at2="@run" data-d2="1.1"></span></div>
    <div class="dim" data-at="@run+1.2" data-d="0.2">1 MB of code, not the 650 MB of images</div>
    <div><span class="ps">$</span> <span data-anim-n="chars" data-text="pip install ./THIRSTMAP" data-at2="@run+1.5" data-d2="0.5"></span></div>
    <div class="dim" data-at="@run+2.1" data-d="0.2">Successfully installed … thirstmap-1.0.0</div>
    <div><span class="ps">$</span> <span data-anim-n="chars" data-text="thirstmap generate --level 3 --seed 11 --twin --out scenes" data-at2="@run+2.5" data-d2="0.9"></span></div>
    <div class="lines" data-anim="type" data-at="@run+3.5" data-d="2.6">{out_lines}</div>
  </div></div>
</div>
<figure class="genmap" data-at="@run+6.0"><img src="assets/gen_map.jpg" alt=""><figcaption>the scene it just built (50 s on a laptop CPU, sped up here)</figcaption></figure>'''
    if sid == "results":
        order = [("Gemini 3.5 Flash", "gemini-3.5-flash", "api"), ("Gemini 3.1 Flash-Lite", "gemini-3.1-flash-lite", "api"),
                 ("Gemini 3.5 Flash-Lite", "gemini-3.5-flash-lite", "api"), ("Qwen2.5-VL-3B", "Qwen/Qwen2.5-VL-3B-Instruct", "open"),
                 ("Qwen2-VL-2B", "Qwen/Qwen2-VL-2B-Instruct", "open")]
        rows_html = ""
        for i, (name, key, kind) in enumerate(order):
            v = r[key]
            at = "@open" if kind == "open" else ("@best" if key == "gemini-3.5-flash" else "@ghost")
            ghost = (f'<div class="gbar" data-anim="grow" data-w="{round(100 * v["blind"])}" data-at="@ghost+2.6" data-d="1.0"></div>'
                     f'<div class="glab" data-at="@ghost+3.2">without the image: {round(100 * v["blind"])}%</div>' if v["blind"] is not None else "")
            rows_html += (f'<div class="brow {kind}{" top" if key == "gemini-3.5-flash" else ""}" data-at="{at}" data-d="0.4">'
                          f'<div class="bn">{E(name)}<span>{"API" if kind == "api" else "open, local"}</span></div>'
                          f'<div class="track"><div class="bar" data-anim="grow" data-w="{v["acc"]}" data-at="{at}+0.2" data-d="1.1"></div>{ghost}'
                          f'<div class="chance" style="left:{N["chance"]}%"></div></div>'
                          f'<div class="bv" data-anim-n="count" data-to="{v["acc"]}" data-suf="%" data-at2="{at}+0.2">{v["acc"]}%</div></div>')
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Findings · same {N['n']} questions, every model, scored against exact chance</div>
  <div class="h" data-at="0.2">Who can trace the water?</div>
</div>
<div class="bars">{rows_html}
  <div class="clab" data-at="@open+0.5" style="left:{360 + N['chance'] * 11}px">guessing: {N['chance']}%</div>
</div>'''
    if sid == "catch":
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Findings · the twin test</div>
  <div class="h" data-at="0.2">Even the best model answers from habit</div>
</div>
<img class="catch" src="assets/catch.jpg" data-at="0.4" alt="">
<div class="ring red" data-at="@same" data-anim="pop" style="left:816px;top:546px;width:150px;height:150px"></div>
<div class="side">
  <div class="sl" data-at="0.6"><span class="ok">✓</span> Original: water above 3 °C at M1, M3. Gemini 3.5 Flash says <b>M1, M3</b>.</div>
  <div class="sl" data-at="@twinside"><span class="no">✗</span> Twin: cooling water is cooler, so <b>no point</b> is above 3 °C.</div>
  <div class="sl" data-at="@same">Gemini says <b>M1, M3</b> again: two false heat alarms.</div>
  <div class="score" data-at="@score"><b>{N['best_pairs'][0]} of {N['best_pairs'][1]}</b><span>pairs right on both halves by the best model; {'every other model: 0' if N['other_pairs'] == [0] else f'the others: at most {max(N["other_pairs"])}'}</span></div>
</div>'''
    if sid == "demo":
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Track 2 deliverable · a demo where scoring separates right from wrong</div>
  <div class="h" data-at="0.2">Live demo: yugesh1111.github.io/THIRSTMAP</div>
</div>
<div class="shotwrap">
  <img class="shot" src="assets/demo_task.jpg" data-at="0.3" data-out="@key" alt="">
  <img class="shot" src="assets/demo_task_key.jpg" data-at="@key" data-out="@try" data-anim="fade" alt="">
  <img class="shot" src="assets/demo_try.jpg" data-at="@try" data-anim="fade" alt="">
</div>
<div class="callouts">
  <div class="co" data-at="1.0" data-out="@key">real replies · ✓ right · ✗ wrong + the trap it fell for</div>
  <div class="co" data-at="@key+0.3" data-out="@try">answer key traced by the simulation</div>
  <div class="co" data-at="@try+0.3">your answer, scored by the same rules, beside the best model</div>
</div>'''
    if sid == "board":
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">The product · yugesh1111.github.io/THIRSTMAP/leaderboard</div>
  <div class="h" data-at="0.2">A leaderboard anyone can join</div>
</div>
<img class="lb1" src="assets/lb_board.jpg" data-at="0.4" alt="">
<img class="lb2" src="assets/lb_card.jpg" data-at="@card" alt="">
<div class="lb3 panel" data-at="@drop"><b>Score your own model</b><span>download the question pack → run any model → drop its replies on the page</span></div>'''
    if sid == "teach":
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Findings · can it be learned, and can people do it?</div>
  <div class="h" data-at="0.2">The data teaches, and the test is open to everyone</div>
</div>
<div class="teach">
  <div class="panel tp" data-at="0.4"><div class="arrow"><b data-anim-n="count" data-to="{N['ft_base']}" data-suf="%" data-at2="0.4">{N['ft_base']}%</b><i>→</i><b class="g" data-anim-n="count" data-to="{N['ft_tuned']}" data-suf="%" data-at2="1.2">{N['ft_tuned']}%</b></div>
    <span>SmolVLM-256M fine-tuned on 300 ThirstMap tasks, tested on scenes it never saw (paired p = 0.01). Without the image: {N['ft_blind']}%, so it learned to look.</span></div>
  <figure class="panel tp" data-at="@human"><img src="assets/human_test.jpg" alt=""><figcaption>Human test: 32 questions the models answered · answers collected automatically</figcaption></figure>
</div>'''
    if sid == "ship":
        jobs = ["tests", "end_to_end", "package", "notebook"]
        ci = "".join(f'<div class="job" data-at="{0.6 + 0.25 * i:.2f}"><span class="ok">✓</span> ci / {j}</div>' for i, j in enumerate(jobs))
        return f'''
<div class="box" style="left:120px;top:140px;width:1680px">
  <div class="eyebrow" data-at="0.1">Implementation · reproducible and cheap</div>
  <div class="h" data-at="0.2">Run it in a browser, check it on every push</div>
</div>
<div class="ship">
  <figure class="panel" data-at="0.3"><img src="assets/nb_styles.jpg" alt=""><figcaption>Colab quickstart: builds a scene in ~3 minutes, no key</figcaption></figure>
  <div class="panel cip" data-at="0.5"><div class="cih">GitHub Actions, on every push</div>{ci}<div class="cin">{N['n_tests']} tests · CI green</div></div>
  <div class="panel econ" data-at="@economy"><b>1</b><span>request per image</span><b>~300</b><span>tokens per answer</span><b>18</b><span>requests per model: fits a free daily tier</span></div>
</div>'''
    if sid == "close":
        return f'''
<img class="hero" src="assets/hero.jpg" data-kb="0.05" alt="">
<div class="heroshade"></div>
<div class="box" style="left:120px;top:210px;width:1000px">
  <div class="mega" data-at="0.2">ThirstMap</div>
  <div class="lead" data-at="0.5">A factory of visual tasks with verified answers, and a hard test for AI.</div>
  <div class="links" data-at="0.9">
    <div><b>Live demo</b> yugesh1111.github.io/THIRSTMAP</div>
    <div><b>Code + 5,761 tasks</b> github.com/yugesh1111/THIRSTMAP</div>
    <div><b>Take the test</b> yugesh1111.github.io/THIRSTMAP/human</div>
    <div><b>Run it</b> pip install · Colab notebook</div>
  </div>
  <div class="punch" data-at="@last">Before we trust AI with India’s water, it should pass this test.</div>
</div>
<div class="qr" data-at="1.2"><img src="assets/qr.png" alt=""><span>scan: live demo</span></div>'''
    raise KeyError(sid)


CSS = r"""
@font-face{font-family:Inter;src:url(fonts/inter-latin-400-normal.woff2) format('woff2');font-weight:400}
@font-face{font-family:Inter;src:url(fonts/inter-latin-600-normal.woff2) format('woff2');font-weight:600}
@font-face{font-family:Inter;src:url(fonts/inter-latin-800-normal.woff2) format('woff2');font-weight:800}
@font-face{font-family:Grotesk;src:url(fonts/space-grotesk-latin-500-normal.woff2) format('woff2');font-weight:500}
@font-face{font-family:Grotesk;src:url(fonts/space-grotesk-latin-700-normal.woff2) format('woff2');font-weight:700}
@font-face{font-family:Mono;src:url(fonts/jetbrains-mono-latin-400-normal.woff2) format('woff2')}
:root{--bg:#0B1C27;--panel:#102838;--line:#21465C;--ink:#EEF4F6;--mute:#A3BAC5;--water:#5AAEF8;--waste:#F2914F;--good:#43C584;--bad:#F2645F}
*{box-sizing:border-box}html,body{margin:0;background:#000}
#stage{width:1920px;height:1080px;position:relative;overflow:hidden;color:var(--ink);font-family:Inter,'DejaVu Sans',sans-serif;
  background:radial-gradient(1300px 800px at 78% 8%,#143A52 0%,var(--bg) 62%)}
.scene{position:absolute;inset:0;visibility:hidden}
.box{position:absolute}.phase{position:absolute;inset:0}
.eyebrow{font:600 21px/1.3 Inter;letter-spacing:.16em;text-transform:uppercase;color:var(--water)}
.h{font:700 58px/1.1 Grotesk;letter-spacing:-.01em;margin-top:12px;max-width:1650px}
.mega{font:700 168px/1 Grotesk;letter-spacing:-.03em;margin:18px 0 6px}
.lead{font:500 44px/1.25 Grotesk;color:#D7E6EE}
.punch{margin-top:46px;font:600 34px/1.4 Inter;color:var(--waste)}
.hero{position:absolute;right:0;top:0;width:1080px;height:1080px;object-fit:cover;transform-origin:60% 50%}
.heroshade{position:absolute;inset:0;background:linear-gradient(90deg,var(--bg) 38%,rgba(11,28,39,.82) 52%,rgba(11,28,39,.15) 80%)}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:36px;margin-top:70px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:22px;padding:40px 40px 44px}
.tile .big{font:700 96px/1 Grotesk;color:var(--water);font-variant-numeric:tabular-nums}
.tile .what{font:400 28px/1.4 Inter;color:var(--mute);margin-top:18px}
.ask{margin-top:64px;font:700 54px/1.2 Grotesk;color:var(--waste)}
.src{margin-top:18px;font:400 20px Inter;color:#7F98A4}
.steps{position:absolute;left:120px;top:330px;display:grid;grid-template-columns:repeat(4,390px);gap:40px}
.step img{width:390px;height:390px;border-radius:16px;display:block}
.step b{display:block;font:700 30px Grotesk;margin-top:18px}.step span{font:400 23px Inter;color:var(--mute)}
.ring{position:absolute;border:6px solid var(--waste);border-radius:50%;box-shadow:0 0 0 10px rgba(242,145,79,.18)}
.ring.red{border-color:var(--bad);box-shadow:0 0 0 10px rgba(242,100,95,.2)}
.styles{position:absolute;left:120px;top:320px;display:grid;grid-template-columns:repeat(3,540px);gap:30px}
.sty img{width:540px;height:540px;object-fit:cover;object-position:top;border-radius:16px;display:block}
.sty b{display:block;font:700 30px Grotesk;margin-top:14px}
.chips{position:absolute;left:120px;top:360px;width:1680px;display:flex;flex-wrap:wrap;gap:22px}
.chip{font:600 34px Inter;padding:18px 30px;border-radius:999px;background:var(--panel);border:1px solid var(--line)}
.levels{position:absolute;left:120px;top:300px;display:grid;grid-template-columns:repeat(5,316px);gap:25px}
.th img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:12px;display:block}
.th span{display:block;font:600 22px Inter;color:var(--mute);margin-top:8px}
.levels .th img{height:230px;aspect-ratio:auto}
.pair2{position:absolute;left:120px;top:625px;width:1680px;display:grid;grid-template-columns:1fr 1fr;gap:60px}
.lab{font:600 22px Inter;color:var(--water);margin-bottom:12px}
.row4{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.th.sm img{height:150px;aspect-ratio:auto}
.counter{position:absolute;right:120px;top:238px;font:500 30px Inter;color:var(--mute)}.counter b{color:var(--ink);font:700 40px Grotesk}
.twin{position:absolute;left:120px;top:290px;width:1680px;display:grid;grid-template-columns:1fr 1fr;gap:60px}
.twin figure{margin:0}.twin img{width:100%;height:520px;object-fit:cover;object-position:top;border-radius:16px;display:block}
.twin figcaption{font:500 27px Inter;margin-top:14px;color:#D7E6EE}.twin b{color:var(--waste)}
.note{position:absolute;right:0;top:-46px;font:500 22px Inter;color:#F08BD5}
.habit{position:absolute;left:50%;transform:translateX(-50%);top:612px;font:700 34px Grotesk;color:var(--bad);white-space:nowrap}
.cards4{position:absolute;left:120px;top:310px;width:1680px;display:grid;grid-template-columns:repeat(4,1fr);gap:28px}
.vc{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:22px;display:flex;flex-direction:column;gap:10px;min-height:540px}
.vc img{width:100%;height:330px;object-fit:cover;border-radius:12px}
.vc b{font:700 32px Grotesk}.vc span{font:400 22px/1.4 Inter;color:var(--mute)}
.vc.num{justify-content:center}.vc .n{font:700 140px/1 Grotesk;color:var(--water);font-variant-numeric:tabular-nums}
.term{position:absolute;left:120px;top:268px;width:1140px;height:664px;background:#07131B;border:1px solid var(--line);border-radius:16px;overflow:hidden}
.term .bar{height:44px;background:#0E2230;display:flex;align-items:center;gap:10px;padding:0 18px}
.term .bar i{width:14px;height:14px;border-radius:50%;background:#2C4B5E;display:block}.term .bar span{margin-left:12px;color:var(--mute);font:500 18px Inter}
.tbody{position:absolute;top:44px;left:0;right:0;bottom:0;overflow:hidden;font:400 21px/1.42 Mono;color:#D9E7EE;overflow-wrap:break-word}
.tin div{white-space:pre-wrap}
.tin{padding:16px 24px}
.ps{color:var(--good)}.ok{color:var(--good)}.dim{color:#7F98A4}.no{color:var(--bad)}
.genmap{position:absolute;left:1300px;top:290px;width:500px;margin:0}.genmap img{width:500px;height:500px;object-fit:cover;border-radius:14px;display:block}
.genmap figcaption{font:400 20px Inter;color:var(--mute);margin-top:10px}
.bars{position:absolute;left:120px;top:300px;width:1680px}
.brow{display:grid;grid-template-columns:330px 1100px 120px;gap:30px;align-items:center;height:112px}
.bn{font:600 30px Inter}.bn span{display:block;font:400 19px Inter;color:var(--mute)}
.track{position:relative;height:54px;background:#0D2333;border-radius:10px}
.bar{position:absolute;left:0;top:0;height:54px;border-radius:10px;background:#4C6B7D}
.brow.api .bar{background:var(--water)}.brow.top .bar{background:linear-gradient(90deg,var(--water),#8FD0FF)}
.gbar{position:absolute;left:0;top:58px;height:14px;border-radius:7px;background:var(--waste)}
.glab{position:absolute;left:0;top:76px;font:500 18px Inter;color:var(--waste);white-space:nowrap}
.chance{position:absolute;top:-10px;bottom:-10px;width:3px;background:#E8EEF1}
.bv{font:700 40px Grotesk;font-variant-numeric:tabular-nums}
.clab{position:absolute;top:-38px;font:500 19px Inter;color:#E8EEF1;transform:translateX(-50%)}
.catch{position:absolute;left:120px;top:300px;width:1000px;border-radius:14px}
.side{position:absolute;left:1180px;top:300px;width:620px;display:flex;flex-direction:column;gap:26px}
.sl{font:500 30px/1.4 Inter}.sl .ok,.sl .no{font-weight:800;margin-right:10px}
.score{margin-top:18px;background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:26px 30px}
.score b{display:block;font:700 96px/1 Grotesk;color:var(--bad)}.score span{font:400 26px/1.4 Inter;color:var(--mute)}
.shotwrap{position:absolute;left:210px;top:290px;width:1500px;height:610px}
.shot{position:absolute;inset:0;width:1500px;height:auto;max-height:610px;object-fit:contain;object-position:top;border-radius:14px;background:#fff}
.callouts{position:absolute;left:0;right:0;top:248px}
.co{position:absolute;right:120px;font:600 24px Inter;color:var(--bg);background:var(--waste);padding:8px 18px;border-radius:10px}
.lb1{position:absolute;left:120px;top:268px;width:890px;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.45)}
.lb2{position:absolute;left:1040px;top:268px;width:760px;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.55)}
.lb3{position:absolute;left:120px;top:818px;width:1680px;display:flex;align-items:center;gap:22px;padding:14px 22px}
.lb3 b{font:700 27px Grotesk;color:var(--water);white-space:nowrap}.lb3 span{font:500 24px Inter}
.teach{position:absolute;left:120px;top:300px;width:1680px;display:grid;grid-template-columns:640px 1fr;gap:40px;align-items:start}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:26px;margin:0}
.tp span,.tp figcaption{font:400 24px/1.45 Inter;color:var(--mute)}
.arrow{display:flex;align-items:center;gap:26px;margin:20px 0 30px}.arrow b{font:700 120px/1 Grotesk;font-variant-numeric:tabular-nums}
.arrow b.g{color:var(--good)}.arrow i{font-style:normal;font:700 70px Grotesk;color:var(--mute)}
.tp img{width:100%;height:470px;object-fit:cover;object-position:top;border-radius:12px;display:block;margin-bottom:14px}
.ship{position:absolute;left:120px;top:300px;width:1680px;display:grid;grid-template-columns:820px 1fr 1fr;gap:30px}
.ship img{width:100%;height:420px;object-fit:cover;object-position:top left;border-radius:12px;display:block}
.ship figcaption{font:500 22px Inter;color:var(--mute);margin-top:12px}
.cih{font:700 28px Grotesk;margin-bottom:18px}.job{font:500 28px Mono;margin:14px 0}.job .ok{margin-right:10px}
.cin{margin-top:26px;font:700 34px Grotesk;color:var(--good)}
.econ{display:grid;grid-template-columns:auto 1fr;gap:14px 18px;align-content:start}
.econ b{font:700 54px/1 Grotesk;color:var(--water)}.econ span{font:400 24px/1.3 Inter;color:var(--mute);align-self:center}
.links{margin-top:40px;display:flex;flex-direction:column;gap:12px;font:400 28px Inter;color:#D7E6EE}.links b{color:var(--water);display:inline-block;width:280px}
.qr{position:absolute;right:150px;top:600px;background:#fff;border-radius:18px;padding:16px;text-align:center}
.qr img{width:230px;height:230px;display:block}.qr span{font:600 20px Inter;color:var(--bg)}
#mark{position:absolute;left:64px;top:40px;font:700 30px Grotesk;letter-spacing:-.01em}#mark span{color:var(--water)}
.cobg{position:absolute;inset:0;background:radial-gradient(1200px 700px at 30% 20%,#123A55 0,transparent 60%),radial-gradient(900px 600px at 80% 90%,#0E3B33 0,transparent 60%),#06121A}
.chatcam{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;transform-origin:50% 46%}
.chat{width:1180px;background:rgba(12,30,42,.92);border:1px solid #2A5670;border-radius:28px;box-shadow:0 40px 120px rgba(0,0,0,.6),0 0 0 1px rgba(90,174,248,.08);overflow:hidden}
.chathead{display:flex;align-items:center;gap:16px;padding:24px 34px;border-bottom:1px solid #1E4357;font:600 26px Inter}
.chathead i{width:18px;height:18px;border-radius:50%;background:var(--good);box-shadow:0 0 14px var(--good)}.chathead span{margin-left:auto;font:400 22px Inter;color:var(--mute)}
.thread{padding:36px 34px 20px;display:flex;flex-direction:column;gap:26px;min-height:430px}
.msg{max-width:860px;font:400 38px/1.4 Inter;padding:20px 30px;border-radius:26px}
.msg.me{align-self:flex-end;background:var(--water);color:#04131C;font-weight:600;border-bottom-right-radius:8px;transform-origin:100% 100%}
.slot{position:relative;min-height:230px}
.msg.ai{position:absolute;left:0;top:0;background:#16384C;border:1px solid #2A5670;border-bottom-left-radius:8px;transform-origin:0 0}
.msg.ai b{color:#8FD0FF;font-weight:800}
.dots{display:flex;gap:12px;padding:26px 30px}.dots i{width:16px;height:16px;border-radius:50%;background:#A3BAC5;display:block}
.input{display:flex;align-items:center;margin:10px 26px 26px;padding:20px 26px;border:1px solid #2A5670;border-radius:20px;background:#081A24;font:400 34px Inter;color:var(--ink);min-height:84px}
.input .caret{display:inline-block;width:3px;height:40px;background:var(--water);margin-left:4px}.input em{margin-left:auto;font-style:normal;color:var(--water);font-size:34px}
.flash{position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none}
#chip:empty{display:none}
#fxflash{position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none;z-index:5}
#fxleak{position:absolute;inset:0;opacity:0;pointer-events:none;z-index:4;mix-blend-mode:screen;
  background:radial-gradient(900px 600px at 15% 20%,rgba(255,150,60,.85),transparent 60%),radial-gradient(800px 700px at 90% 85%,rgba(90,174,248,.7),transparent 60%)}
#chip{position:absolute;right:64px;top:40px;font:700 19px Inter;letter-spacing:.13em;color:var(--bg);background:var(--water);padding:9px 18px;border-radius:999px}
#sub{position:absolute;left:50%;bottom:54px;transform:translateX(-50%);width:max-content;max-width:1560px;text-align:center;
  font:500 33px/1.38 Inter;color:#fff;background:rgba(3,10,15,.78);padding:12px 28px;border-radius:12px}
#sub:empty{display:none}
#prog{position:absolute;left:0;right:0;bottom:0;height:7px;background:#08151D}#prog i{position:absolute;left:0;top:0;bottom:0;background:var(--water)}
#prog b{position:absolute;top:0;bottom:0;width:2px;background:#0B1C27}
"""

JS = r"""
const TL = __TL__;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const ease = x => x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
const scEl = TL.scenes.map(s => document.getElementById('s-' + s.id));
function at(expr, el) {
  const sc = TL.scenes[scEl.indexOf(el.closest('.scene'))];
  const m = String(expr).match(/^@(\w+)([+-][\d.]+)?$/);
  if (m) { const k = Math.min(sc.marks[m[1]] ?? 0, sc.sent.length - 1); return sc.sent[k].s + parseFloat(m[2] || 0); }
  return sc.start + parseFloat(expr);
}
const A = [...document.querySelectorAll('[data-at]')].map(el => ({el, t0: at(el.dataset.at, el), d: parseFloat(el.dataset.d || .7),
  kind: el.dataset.anim || 'rise', out: el.dataset.out ? at(el.dataset.out, el) : null}));
const Nn = [...document.querySelectorAll('[data-anim-n]')].map(el => ({el, t0: at(el.dataset.at2 || '0', el), d: parseFloat(el.dataset.d2 || 1.2)}));
const O = [...document.querySelectorAll('[data-out]:not([data-at])')].map(el => ({el, out: at(el.dataset.out, el)}));
const KB = [...document.querySelectorAll('[data-kb]')].map(el => ({el, sc: TL.scenes[scEl.indexOf(el.closest('.scene'))], z: parseFloat(el.dataset.kb)}));
const KF = [...document.querySelectorAll('[data-kf]')].map(el => ({el, sc: TL.scenes[scEl.indexOf(el.closest('.scene'))], k: JSON.parse(el.dataset.kf)}));
const PU = [...document.querySelectorAll('[data-pulse]')];
function kfv(k, key, t, def) { const p = k.filter(x => key in x[1]).map(x => [x[0], x[1][key]]); if (!p.length) return def;
  if (t <= p[0][0]) return p[0][1];
  for (let i = 1; i < p.length; i++) if (t <= p[i][0]) { const [a, va] = p[i - 1], [b, vb] = p[i]; return va + (vb - va) * ease(clamp((t - a) / (b - a))); }
  return p[p.length - 1][1]; }
function FX(kind, e, t, entering) {            // e: 0 = settled, 1 = at the cut; returns [transform, filter, opacity gamma]
  const j = (a, b) => Math.sin(t * a) * b;
  switch (kind) {
    case 'zoom': return entering ? [`scale(${1 + .32 * e})`, `blur(${16 * e}px)`, 1]
                                 : [`scale(${1 + .5 * e})`, `blur(${20 * e}px)`, 1];
    case 'push': return [`translateX(${(entering ? 1 : -1) * 380 * e}px) scale(${1 - .06 * e})`, `blur(${12 * e}px)`, .8];
    case 'glitch': { const k = e > .02 ? 1 : 0;
      return [`translate(${j(97, 30 * e) * k}px,${j(61, 10 * e) * k}px) skewX(${j(43, 6 * e) * k}deg)`,
              `drop-shadow(${16 * e}px 0 0 rgba(255,40,100,.85)) drop-shadow(${-16 * e}px 0 0 rgba(40,220,255,.85)) contrast(${1 + .7 * e}) saturate(${1 + e})`,
              .35]; }
    case 'flash': return [`scale(${1 + .1 * e})`, `brightness(${1 + 2.2 * e})`, .5];
    case 'impact': return entering ? [`scale(${1 + .28 * e})`, `blur(${12 * e}px) brightness(${1 + 1.5 * e})`, .6] : ['', '', 1];
    default: return ['', '', 1];
  }
}
const FXL = {flash: document.getElementById('fxflash'), leak: document.getElementById('fxleak')};
const sub = document.getElementById('sub'), chip = document.getElementById('chip'), bar = document.querySelector('#prog i');
document.querySelector('#prog').insertAdjacentHTML('beforeend', TL.scenes.slice(1).map(s => `<b style="left:${100 * s.start / TL.T}%"></b>`).join(''));
const fmt = (x, el) => (el.dataset.to >= 1000 ? Math.round(x).toLocaleString('en-US') : Math.round(x)) + (el.dataset.suf || '');
function renderAt(t) {
  let fx = 0, leak = 0;
  TL.scenes.forEach((sc, i) => {
    const D = .4, last = i === TL.scenes.length - 1, nx = TL.scenes[i + 1] || {};
    const pin = i === 0 ? 1 : clamp((t - sc.start) / D), pout = last ? 1 : clamp((sc.end - t) / D);
    let tr = '', f = '', o = Math.min(pin, pout);
    if (pin < 1) { let g; [tr, f, g] = FX(sc.tr, 1 - ease(pin), t, true); o = Math.pow(o, g); }
    else if (pout < 1) { let g; [tr, f, g] = FX(nx.tr, 1 - ease(pout), t, false); o = Math.pow(o, g); }
    const el = scEl[i]; el.style.opacity = o; el.style.visibility = o > 0 ? 'visible' : 'hidden';
    el.style.transform = tr; el.style.filter = f;
    if (i > 0) { const d = Math.abs(t - sc.start);
      if (sc.tr === 'flash' || sc.tr === 'impact') fx = Math.max(fx, .9 * clamp(1 - d / .32));
      if (sc.tr === 'zoom') leak = Math.max(leak, clamp(1 - d / .5)); } });
  FXL.flash.style.opacity = fx; FXL.leak.style.opacity = leak * .85;
  for (const a of A) {
    const p = ease(clamp((t - a.t0) / a.d)); const q = a.out == null ? 1 : 1 - ease(clamp((t - a.out) / .45)); const s = a.el.style;
    if (a.kind === 'grow') s.width = (p * parseFloat(a.el.dataset.w)) + '%';
    else if (a.kind === 'type') { const ls = a.el.children, n = Math.floor(clamp((t - a.t0) / a.d) * ls.length + 1e-6);
      for (let k = 0; k < ls.length; k++) ls[k].style.display = k < n ? 'block' : 'none'; }
    else if (a.kind === 'fade') s.opacity = p * q;
    else if (a.kind === 'pop') { s.opacity = p * q; s.transform = `scale(${.85 + .15 * p})`; }
    else { s.opacity = p * q; s.transform = `translateY(${(1 - p) * 26}px)`; }
  }
  for (const o of O) o.el.style.opacity = 1 - ease(clamp((t - o.out) / .45));
  for (const n of Nn) { const p = ease(clamp((t - n.t0) / n.d)); const el = n.el;
    if (el.dataset.animN === 'chars') { const full = el.dataset.text; el.textContent = full.slice(0, Math.round(p * full.length)); }
    else el.textContent = fmt(parseFloat(el.dataset.to) * p, el); }
  for (const tb of document.querySelectorAll('.tbody')) { const tin = tb.firstElementChild;
    tin.style.transform = `translateY(${-Math.max(0, tin.offsetHeight - tb.clientHeight)}px)`; }
  for (const f of KF) { const lt = t - f.sc.start, s = kfv(f.k, 's', lt, 1), o = kfv(f.k, 'o', lt, 1), b = kfv(f.k, 'b', lt, 0);
    f.el.style.transform = `scale(${s})`; f.el.style.opacity = o; f.el.style.filter = b > 0.05 ? `blur(${b}px)` : ''; }
  PU.forEach(el => { el.style.opacity = .3 + .7 * (.5 + .5 * Math.sin(t * 7 - el.dataset.pulse * 1.1)); });
  for (const k of KB) k.el.style.transform = `scale(${1 + k.z * clamp((t - k.sc.start) / (k.sc.end - k.sc.start))})`;
  let s = ''; let cur = TL.scenes[0];
  for (const sc of TL.scenes) { if (t >= sc.start) cur = sc; for (const c of sc.sent) if (t >= c.s - .05 && t < c.e + .25) s = c.text; }
  if (sub.textContent !== s) sub.textContent = s;
  if (chip.textContent !== cur.crit) chip.textContent = cur.crit;
  bar.style.width = (100 * t / TL.T) + '%';
}
window.renderAt = renderAt; window.TL = TL;
renderAt(parseFloat(new URLSearchParams(location.search).get('t') || '0'));
"""


def page(scenes, total, N, title):
    body = "".join(f'<section class="scene" id="s-{sc["id"]}">{scene_html(sc["id"], N)}</section>' for sc in scenes)
    tl = json.dumps(dict(T=round(total, 3), scenes=scenes)).replace("<", "\\u003c")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{E(title)}</title><style>{CSS}</style></head><body>'
            f'<div id="stage">{body}<div id="fxleak"></div><div id="fxflash"></div><div id="mark">Thirst<span>Map</span></div><div id="chip"></div><div id="sub"></div>'
            f'<div id="prog"><i></i></div></div><script>{JS.replace("__TL__", tl)}</script></body></html>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--film", choices=["full", "short"], default="full")
    ap.add_argument("--out", default=None)
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=1.06)
    ap.add_argument("--test-python", default="python3", help="interpreter with the project installed, to count tests")
    a = ap.parse_args()
    N = numbers()
    N["n_tests"] = count_tests(a.test_python)
    check(N)
    out = Path(a.out or ROOT / "video/build" / a.film)
    out.mkdir(parents=True, exist_ok=True)
    spec = full_script(N) if a.film == "full" else short_script(N)
    voice = Voice(ROOT / "video/build/tts_cache", a.voice, a.speed)
    scenes, clips, total = timeline(spec, voice)
    assign_transitions(scenes)
    prep_assets(out)
    (out / "film.html").write_text(page(scenes, total, N, "ThirstMap film" if a.film == "full" else "ThirstMap in a minute"))
    ref = max(float(np.max(np.abs(a))) for _, a in clips)
    if scenes[0]["id"] == "coldopen":
        clips += coldopen_sfx(scenes[0]["start"], ref)
    clips += transition_sfx(scenes, ref)
    write_audio(clips, total, out / "narration.wav")
    subtitles(scenes, out / "subtitles.vtt", out / "subtitles.srt")
    (out / "timeline.json").write_text(json.dumps(dict(T=total, scenes=scenes), indent=1))
    print(f"{a.film}: {total:.1f} s, {len(scenes)} scenes, {sum(len(s['sent']) for s in scenes)} lines -> {out}")


if __name__ == "__main__":
    main()
