"""Make the eight README walkthrough GIFs (docs/gifs/walkthrough/0_*.gif ... 7_*.gif).

    python -m http.server 8799 --bind 127.0.0.1 --directory .          # in another shell, from the repo root
    node video/walkthrough/capture.js http://127.0.0.1:8799 video/build/walkthrough
    python video/walkthrough/steps.py --quick-log quick_log.json         # all steps; or name some: 1 5 7

Every picture is real: captures of docs/demo, docs/leaderboard and human_eval (capture.js), images from docs/demo
and the films' rebuilt scenes (video/film_scenes.py), and for step 0 the timed output of a real `./run_all.sh --quick`
(record it with video/walkthrough/time_quick_run.py). Titles, captions and camera moves are added here. Numbers in the
captions are the ones the pages, the result files and docs/VALIDATION_REPORT.md show.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
from kit import AMBER, BLUE, GREEN, RED, H, W, Film, canvas, cursor, fit, glow, img, lerp, map_rect, overlay, place, spotlight  # noqa: E402,E501

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "video/build/walkthrough"
OUT = ROOT / "docs/gifs/walkthrough"
PIPE = ROOT / "docs/demo/pipeline"
DEMO_IMG = ROOT / "docs/demo/img"
SCENES = ROOT / "video/build/dataset"
kit.OVERLAYS = CAP
META = {}
OV = {}                                           # overlay name -> html, filled by the step definitions below


# ---- overlay templates ----------------------------------------------------------------------------------------------
def title(key, n, plain, grad, sub, pills):
    OV[key] = (f'<div class="full" style="padding:140px 80px 0"><div class="kicker">ThirstMap · step {n} of 7</div>'
               f'<div class="big" style="margin-top:18px">{plain} <span class="grad">{grad}</span></div>'
               f'<div class="sub" style="margin-top:18px;max-width:700px">{sub}</div>'
               f'<div class="row">{"".join(f"<span class=pill>{p}</span>" for p in pills)}</div></div>')


def end(key, kicker, line1, line2, stats, url):
    cells = "".join(f'<div class="stat"><b class="{c}">{v}</b><span>{t}</span></div>' for v, t, c in stats)
    OV[key] = (f'<div class="full" style="padding:112px 72px 0"><div class="kicker">{kicker}</div>'
               f'<div class="big" style="font-size:44px;margin-top:16px">{line1}<br><span class="grad">{line2}</span></div>'
               f'<div class="row" style="margin-top:34px">{cells}</div>'
               f'<div style="margin-top:30px" class="url">{url}</div></div>')


def cap(key, badge, text, tone=""):
    OV[key] = f'<div class="cap"><span class="n {tone}">{badge}</span><span>{text}</span></div>'


def panel(key, num, head, body, width=372):
    OV[key] = (f'<div class="full" style="padding:118px 0 0 52px"><div style="width:{width}px">'
               f'<span class="n" style="font-size:14px">{num}</span>'
               f'<div class="mid" style="margin-top:14px">{head}</div>'
               f'<div class="body" style="margin-top:14px">{body}</div></div></div>')


def label(key, text, cls="label"):
    OV[key] = f'<span class="{cls}">{text}</span>'


def stamp(key, ok, text):
    OV[key] = f'<div class="stampbox {"ok" if ok else "bad"}">{"✓" if ok else "✗"} <span>{text}</span></div>'


def intro(film, key):
    film.hold(lambda t: _with(canvas(), lambda c: overlay(c, key, t / 0.7, at="full", slide=22)), 1.9)


def outro(film, key, hold=1.4):
    """End on the step's own last frame (no summary slide: each step's numbers are already on screen)."""
    last = film.frames[-1]
    film.hold(lambda t: last, hold)


def _with(c, fn):
    fn(c)
    return c


def center_label(c, key, cx, y, t=1.0):
    o = kit.ov(key)
    overlay(c, key, t, at=(cx - o.width / 2, y), slide=8)


# ---- step 0: one command --------------------------------------------------------------------------------------------
TERM_W, LINE_H, TERM_PAD = 880, 18, 14


def define_step0(log):
    title("t0", 0, "Run it all with", "one command",
          "<span class=mono>./run_all.sh --quick</span> runs the tests, builds a small dataset, scores the offline "
          "baselines, writes the validation report, rebuilds scenes from their seeds and makes the demo pages.",
          ["no API key", "7 stages", "a laptop"])
    lines = [("cmd", "$ ./run_all.sh --quick")] + [("out", l) for _, l in log["lines"] if l is not None]

    def style(kind, s):
        s = s.replace("&", "&amp;").replace("<", "&lt;")
        if kind == "cmd":
            return f'<span style="color:#eef2f4;font-weight:700">{s}</span>'
        if s.startswith("== "):
            return f'<span style="color:#5aa7ff;font-weight:700">{s}</span>'
        if any(k in s for k in ("passed", "report written", "wrote ", "Done.", " -> ")):
            return f'<span style="color:#46d07a">{s}</span>'
        return f'<span style="color:#c9d3d8">{s}</span>'
    body = "".join(f'<div style="height:{LINE_H}px;white-space:pre;overflow:hidden;text-overflow:ellipsis">'
                   f'{style(k, s)}</div>' for k, s in lines)
    OV["t0_lines"] = (f'<div style="width:{TERM_W - 2 * TERM_PAD}px;font:500 12.5px/{LINE_H}px \'JetBrains Mono\',monospace">'
                      f'{body}</div>')
    OV["t0_chrome"] = (f'<div style="width:{TERM_W}px;height:34px;display:flex;align-items:center;padding:0 14px;gap:8px;'
                       'background:#1b2227;border-bottom:1px solid #2a343a;border-radius:12px 12px 0 0">'
                       '<i style="width:12px;height:12px;border-radius:50%;background:#ff5f57"></i>'
                       '<i style="width:12px;height:12px;border-radius:50%;background:#febc2e"></i>'
                       '<i style="width:12px;height:12px;border-radius:50%;background:#28c840"></i>'
                       '<span style="flex:1;text-align:center;font:500 12.5px \'JetBrains Mono\';color:#8b979e">'
                       'thirstmap — ./run_all.sh --quick</span><span style="width:52px"></span></div>')
    total = log["lines"][-1][0]
    end("e0", "One command", "Everything rebuilds from code.", "No API key, no download.",
        [(f"{total:.0f} s", "real time for the quick run on a laptop", "grad"),
         ("7 / 7", "stages finished, 0 errors", ""),
         ("47", "tests pass (3 skipped)", "")],
        "github.com/yugesh1111/THIRSTMAP")
    return lines


def clock_text(sec):
    return f"real time {int(sec) // 60}:{int(sec) % 60:02d}"


def step0(log, lines):
    from PIL import ImageDraw, ImageFont
    import matplotlib
    mono = ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSansMono-Bold.ttf"), 12)
    f = Film()
    intro(f, "t0")
    term = (40, 34, TERM_W, 440)
    body_top, body_h = term[1] + 34 + 10, term[3] - 34 - 20
    visible = body_h // LINE_H
    stamps = [0.0] + [t for t, l in log["lines"] if l is not None]       # line i appears at stamps[i]
    total = log["lines"][-1][0]
    speed = total / 11.0                                                    # 82 s of real time in ~11 s

    def frame(real_t, typed=1.0, blink=True):
        c = canvas()
        kit.shadow(c, term, 12, 170)
        win = kit.Image.new("RGBA", (term[2], term[3]), (14, 19, 22, 255))
        mask = kit.Image.new("L", (term[2], term[3]), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, term[2] - 1, term[3] - 1), 12, fill=255)
        c.paste(win, (term[0], term[1]), mask)
        overlay(c, "t0_chrome", 1, at=(term[0], term[1]), slide=0)
        n = sum(1 for s in stamps if s <= real_t)
        first = max(0, n - visible)
        lines_img = kit.ov("t0_lines")
        crop = lines_img.crop((0, first * LINE_H, lines_img.width, n * LINE_H))
        if n == 1 and typed < 1:                                             # typing the command
            chars = len(lines[0][1])
            cw = 7.55
            crop = crop.crop((0, 0, round(14 + cw * (2 + (chars - 2) * typed)), crop.height))
        c.alpha_composite(crop, (term[0] + TERM_PAD, body_top))
        # block cursor after the last line
        if blink and int(real_t * 2.5 / max(speed, 1) * speed) % 2 == 0 or not blink:
            cy = body_top + (n - first) * LINE_H if n < len(stamps) else body_top + (n - first) * LINE_H
            d = ImageDraw.Draw(c)
            if typed < 1:
                cx = term[0] + TERM_PAD + round(7.55 * (2 + (len(lines[0][1]) - 2) * typed))
                d.rectangle((cx, body_top + 3, cx + 7, body_top + LINE_H - 2), fill=(200, 210, 215, 255))
            elif n >= len(stamps):
                d.text((term[0] + TERM_PAD, cy + 2), "$", fill=(238, 242, 244), font=mono)
                d.rectangle((term[0] + TERM_PAD + 14, cy + 3, term[0] + TERM_PAD + 21, cy + LINE_H - 2), fill=(200, 210, 215))
            else:
                d.rectangle((term[0] + TERM_PAD, cy + 3, term[0] + TERM_PAD + 7, cy + LINE_H - 2), fill=(200, 210, 215))
        d = ImageDraw.Draw(c)
        txt = clock_text(min(real_t, total))
        tw = d.textlength(txt, font=mono)
        d.rounded_rectangle((term[0] + term[2] - tw - 30, term[1] + 7, term[0] + term[2] - 10, term[1] + 27), 7,
                            fill=(42, 34, 14))
        d.text((term[0] + term[2] - tw - 20, term[1] + 10), txt, fill=(240, 196, 92), font=mono)
        return c

    f.fade_to(frame(0, 0.0), 0.4)
    f.tween(lambda e: frame(0, e), 0.9)
    f.hold(lambda t: frame(0, 1.0), 0.3)
    f.hold(lambda t: frame(0.01 + t * speed), total / speed + 0.1)
    f.hold(lambda t: frame(total + 1, blink=False), 1.2)
    outro(f, "e0")
    return f


# ---- step 1: build a task -------------------------------------------------------------------------------------------
def define_step1():
    title("t1", 1, "Build a", "task",
          "The code makes the land, simulates where every drop of water flows, places a data centre and villages, "
          "then works out the answer itself.", ["4 × 4 km", "160 × 160 cells", "same seed, same scene"])
    panel("p1a", "1 · TERRAIN", "Make the land",
          "Fractal terrain, 4 × 4 km on a 160 × 160 grid of 25 m cells. It runs from <b>48 m to 149 m</b>, higher in "
          "the north, so streams drain south.")
    panel("p1b", "2 · WATER", "Let it rain",
          "Hollows fill first, then every cell sends its water to its steepest downhill neighbour. Counting what "
          "flows through each cell draws <b>1,465 stream cells</b>.")
    panel("p1c", "3 · SCENE", "Place the people",
          "Data centre DC-1 and its outfall O, <b>7 villages</b>, 4 wetlands and a water intake. A trap is built in: "
          "V6 is close to DC-1 but on <b>another stream</b>.")
    panel("p1d", "4 · ANSWER", "Trace the water",
          "Follow the flow downhill from O. The wastewater reaches <b>V7, then V4</b>. No model and no person: the "
          "code knew the answer before anyone looked.")
    cap("c1d", "ANSWER", "Wastewater from outfall O reaches <b class=a>V7</b> and <b class=a>V4</b>.", "amber")
    end("e1", "Step 1", "The code built the land,", "so it knows every answer.",
        [("5,330", "verified tasks", "grad"), ("308", "scenes, each from one seed", ""), ("0", "hand-labelled answers", "")],
        "yugesh1111.github.io/THIRSTMAP/#how")


def step1():
    f = Film()
    intro(f, "t1")
    box = (470, 40, 450, 450)
    pics = ["1_terrain.png", "2_water.png", "3_scene.png", "4_answer.png"]

    def frame(k, t, zoom=None, cap_t=0.0):
        c = canvas()
        im = img(PIPE / pics[k])
        z = 1 + 0.05 * min(t / 2.6, 1)                                 # slow push-in
        s = im.width / z
        region = zoom or ((im.width - s) / 2, (im.height - s) / 2, s, s)
        place(c, im, box, region)
        overlay(c, ["p1a", "p1b", "p1c", "p1d"][k], (t - 0.1) / 0.5, at="full")
        if cap_t > 0:
            overlay(c, "c1d", cap_t)
        return c

    for k in range(4):
        f.fade_to(frame(k, 0), 0.45)
        f.hold(lambda t, k=k: frame(k, t), 2.4 if k < 3 else 1.6)
    # follow the answer path: O -> V7 -> V4, then back out
    im = img(PIPE / "4_answer.png")
    s0 = im.width / 1.05
    full = ((im.width - s0) / 2, (im.height - s0) / 2, s0, s0)
    a, b = (150, 70, 250, 250), (330, 380, 230, 230)
    f.tween(lambda e: frame(3, 9, lerp(full, a, e)), 0.6)
    f.hold(lambda t: frame(3, 9, a, t / 0.4), 0.7)
    f.tween(lambda e: frame(3, 9, lerp(a, b, e), 1), 1.1)
    f.hold(lambda t: frame(3, 9, b, 1), 0.8)
    f.tween(lambda e: frame(3, 9, lerp(b, full, e), 1), 0.6)
    f.hold(lambda t: frame(3, 9, full, 1), 0.6)
    outro(f, "e1")
    return f


# ---- step 2: vary it ------------------------------------------------------------------------------------------------
def define_step2():
    title("t2", 2, "Vary", "everything",
          "One answer key, many looks: three image styles, five difficulty levels, real terrain from four Indian "
          "data-centre hubs, and the same scene in rain, haze and a coarse sensor.",
          ["3 styles", "5 levels", "4 real cities", "4 conditions"])
    cap("c2a", "STYLES", "One scene, three image styles. <b>One answer key</b> serves all three.")
    cap("c2b", "LEVELS", "Difficulty 1 → 5: rougher land, more ridges, more <b>distractor streams</b> and villages.")
    cap("c2c", "REAL LAND", "Real Copernicus elevation and ESA land cover for <b>four data-centre hubs</b>.")
    cap("c2d", "CONDITIONS", "Season, haze and sensor change the look, <b>never the answer</b>.")
    for k, t in enumerate(["Satellite-style", "Topographic map", "Thermal, °C above normal"]):
        label(f"l2s{k}", t)
    for k in range(5):
        label(f"l2l{k}", f"Level {k + 1}")
    for k, t in enumerate(["Navi Mumbai", "Hyderabad", "Pune", "Chennai"]):
        label(f"l2c{k}", t)
    for k, t in enumerate(["Dry season", "Monsoon", "Haze", "Coarse sensor"]):
        label(f"l2v{k}", t)
    end("e2", "Step 2", "Change how it looks.", "The answer must not move.",
        [("10", "reasoning skills, no counting", "grad"), ("3 × 5", "styles × difficulty levels", ""),
         ("4", "real Indian data-centre hubs", "")],
        "yugesh1111.github.io/THIRSTMAP")


def _row(c, ims, keys, y, size, gap, t0, t, stagger=0.18, region_fn=None):
    n = len(ims)
    x0 = (W - (n * size + (n - 1) * gap)) / 2
    for i, (im, key) in enumerate(zip(ims, keys)):
        e = kit.ease((t - t0 - stagger * i) / 0.45)
        if e <= 0:
            continue
        rect = (x0 + i * (size + gap), y + (1 - e) * 26, size, size)
        place(c, im, rect, region_fn(im) if region_fn else None, alpha=e, radius=12)
        center_label(c, key, rect[0] + size / 2, y + size + 10, e)


def _square(im):
    s = min(im.width, im.height)
    return ((im.width - s) / 2, (im.height - s) / 2, s, s)


def step2():
    f = Film()
    intro(f, "t2")
    styles = [img(PIPE / n) for n in ("6_satellite.jpg", "6_map.jpg", "6_thermal.jpg")]
    lv = []
    for k in range(1, 6):
        lv.append(img(sorted(DEMO_IMG.glob(f"level{k}_seed*_satellite.jpg"))[0]))
    cities = [img(DEMO_IMG / n) for n in ("real_navi_mumbai_seed31312_satellite.jpg", "real_hyderabad_seed48217_satellite.jpg",
                                          "real_pune_seed47441_satellite.jpg", "real_chennai_seed31409_satellite.jpg")]
    v = SCENES / "variants/level1_seed14596"
    conds = [img(SCENES / "scenes/level1_seed14596/satellite.png")] + [img(v / f"{n}.png") for n in ("monsoon", "haze", "coarse")]

    def group(ims, keys, capkey, size, gap, y):
        def fr(t):
            c = canvas()
            _row(c, ims, keys, y, size, gap, 0, t, region_fn=_square)
            overlay(c, capkey, (t - 0.5) / 0.4)
            return c
        return fr

    for ims, keys, ck, size, gap, y, d in [
            (styles, [f"l2s{k}" for k in range(3)], "c2a", 270, 22, 56, 3.0),
            (lv, [f"l2l{k}" for k in range(5)], "c2b", 168, 14, 120, 3.0),
            (cities, [f"l2c{k}" for k in range(4)], "c2c", 206, 16, 96, 3.0)]:
        fr = group(ims, keys, ck, size, gap, y)
        f.fade_to(fr(0.35), 0.35)
        f.hold(lambda t, fr=fr: fr(t + 0.35), d)

    # conditions: one big frame cycling through the four looks
    box = (W / 2 - 190, 24, 380, 380)

    def cond(k, mix):
        c = canvas()
        a = conds[k]
        place(c, a, box, _square(a))
        if mix > 0:
            place(c, conds[(k + 1) % 4], box, _square(conds[(k + 1) % 4]), alpha=mix, shade=False)
        key = f"l2v{(k + 1) % 4 if mix > 0.5 else k}"
        center_label(c, key, W / 2, box[1] + box[3] + 9)
        overlay(c, "c2d", 1)
        return c

    f.fade_to(cond(0, 0), 0.35)
    f.hold(lambda t: cond(0, 0), 0.8)
    for k in range(3):
        f.tween(lambda e, k=k: cond(k, e), 0.45)
        f.hold(lambda t, k=k: cond(k + 1, 0), 0.8)
    outro(f, "e2")
    return f


# ---- step 3: check every answer -------------------------------------------------------------------------------------
def define_step3():
    title("t3", 3, "Check", "every answer",
          "Two independent checks on every question: a second hydrology library re-derives it, and the answer has to "
          "be visible in the image's own pixels. Failures are dropped, never edited.",
          ["12 validators", "pysheds", "pixel evidence", "nothing hand-edited"])
    panel("p3a", "CHECK 1 · PYSHEDS", "A second opinion",
          "pysheds, a separate hydrology library, recomputes the flow. Here it agrees on <b>99.73% of cells</b> "
          "(red: the 70 that differ) and gives the same answer to <b>10 of 10</b> questions.")
    panel("p3b", "CHECK 2 · PIXELS", "Can you see it?",
          "The answer path must show in the picture the model gets. Each dot is a path cell; green means water is "
          "visible there: <b>137 of 137</b>.")
    panel("p3c", "ALL 308 SCENES", "The record",
          "Every check, every scene. pysheds agrees on <b>99.85%</b> of cells on average; <b>39 questions</b> were "
          "dropped and <b>none edited</b>. All of it is in docs/VALIDATION_REPORT.md.", width=330)
    end("e3", "Step 3", "If a check fails, the question goes.", "Nothing is fixed by hand.",
        [("99.85%", "of cells agree with pysheds, on average", "grad"), ("39", "questions dropped", ""),
         ("0", "answers edited", "")],
        "docs/VALIDATION_REPORT.md")


def step3():
    f = Film()
    intro(f, "t3")
    box = (470, 40, 450, 450)

    def pic(name, pkey):
        def fr(t, region=None):
            c = canvas()
            im = img(PIPE / name)
            z = 1 + 0.06 * min(t / 3, 1)
            s = im.width / z
            place(c, im, box, region or ((im.width - s) / 2, (im.height - s) / 2, s, s))
            overlay(c, pkey, (t - 0.1) / 0.5, at="full")
            return c
        return fr

    for name, key in (("5_check.png", "p3a"), ("7_pixels.jpg", "p3b")):
        fr = pic(name, key)
        f.fade_to(fr(0), 0.45)
        f.hold(fr, 3.2)
    chart = img(ROOT / "docs/validation_pass_rates.png")
    cbox = (420, 60, 510, 510 * chart.height / chart.width)

    def chart_fr(t):
        c = canvas()
        z = 1 + 0.05 * min(t / 3.4, 1)
        w, h = chart.width / z, chart.height / z
        place(c, chart, cbox, ((chart.width - w) * 0.3, (chart.height - h) * 0.3, w, h))
        overlay(c, "p3c", (t - 0.1) / 0.5, at="full")
        return c
    f.fade_to(chart_fr(0), 0.45)
    f.hold(chart_fr, 3.6)
    outro(f, "e3")
    return f


# ---- step 4: test the models ----------------------------------------------------------------------------------------
def define_step4():
    title("t4", 4, "Test the", "models",
          "Frontier and open vision models answer the same water-flow questions. Every reply is scored against the "
          "answer key the code already knows.", ["5 models", "150 questions", "19 before-and-after pairs", "scored automatically"])
    cap("c4a", "77%", "Gemini 3.5 Flash, the best model. <b>Guessing scores 14%.</b>")
    cap("c4b", "IMAGE OFF", 'Hide the picture and Flash-Lite falls to <span class="r">chance</span>: the questions need it.')
    cap("c4c", "TWINS", 'One small change flips the answer. Best model: <span class="r">6 of 19</span> pairs.', "red")
    cap("c4d", "LIVE", "The leaderboard scores every reply <b>in your browser</b>, 150 questions.")
    cap("c4e", "PAIRS", 'Open models: <span class="r">0 of 19</span> pairs. Gemini gets most single questions, few pairs.', "red")
    cap("c4f", "REPORT CARD", 'Click a model: skills, <span class="g">every pair</span>, <span class="r">every mistake</span>.')
    end("e4", "What the tests say", "The best model sees the water.", "It still answers from habit.",
        [("77%", "Gemini 3.5 Flash on 83 shared questions (guessing: 14%)", "grad"),
         ("48% → 15%", "Flash-Lite with the image, then without it", ""),
         ("6 of 19", "pairs right on both halves, best model", "r")],
        "yugesh1111.github.io/THIRSTMAP/leaderboard")


def _cap_img(name):
    return img(CAP / f"{name}.png")


def css(r):
    return tuple(v * kit.S for v in r)


def step4():
    f = Film()
    intro(f, "t4")
    m = META["found"]
    found, cards = _cap_img("found"), m["boxes"]["cards"]
    FULL = (0, 0, m["w"], m["h"])
    stage = (40, 40, W - 80, H - 150)

    def found_fr(region, active=None, a=0.0, capk=None, ct=0.0):
        c = canvas()
        rect = fit(region[2:], stage)
        place(c, found, rect, css(region))
        if active is not None:
            r = map_rect(cards[active], region, rect)
            spotlight(c, r, a)
            glow(c, r, RED if active == 2 else BLUE, a)
        if capk:
            overlay(c, capk, ct)
        return c

    def focus(k):
        x, y, w, h = cards[k]
        reg = [max(0, x - 150), max(0, y - 60), w + 300, h + 120]
        if reg[0] + reg[2] > m["w"]:
            reg[0] = m["w"] - reg[2]
        reg[3] = min(reg[3], m["h"] - reg[1])
        return tuple(reg)

    f.fade_to(found_fr(FULL), 0.4)
    f.hold(lambda t: found_fr(FULL), 0.3)
    prev = FULL
    for k, ck in zip((0, 1, 2), ("c4a", "c4b", "c4c")):
        tgt = focus(k)
        f.tween(lambda e, k=k, p=prev, tgt=tgt: found_fr(lerp(p, tgt, e), k, e), 0.5)
        f.hold(lambda t, k=k, tgt=tgt, ck=ck: found_fr(tgt, k, 1.0, ck, t / 0.4), 1.7)
        prev = tgt
    f.tween(lambda e: found_fr(lerp(prev, FULL, e), 2, 1 - e), 0.5)
    f.hold(lambda t: found_fr(FULL), 0.2)

    m = META["board"]
    board, rows, heads = _cap_img("board"), m["boxes"]["rows"], m["boxes"]["heads"]
    BREG = (0, 0, m["w"], m["h"])
    brect = fit(BREG[2:], (30, 34, W - 60, H - 130))

    def board_fr(t_rows, col_a=0.0, capk=None, ct=0.0):
        c = canvas()
        place(c, board, brect, css(BREG))
        k = brect[2] / m["w"]
        for i, r in enumerate(rows):                       # cover rows that have not arrived yet
            e = kit.ease((t_rows - 0.13 * i) / 0.4)
            if e >= 1:
                continue
            y0 = brect[1] + r[1] * k
            cover = kit.Image.new("RGBA", (round(brect[2]) - 2, round(r[3] * k) + 1), (22, 28, 32, int(255 * (1 - e))))
            c.alpha_composite(cover, (round(brect[0]) + 1, round(y0)))
        if col_a > 0:
            hx, _, hw, _ = heads[5]
            col = (hx - 6, 4, hw + 12, rows[-1][1] + rows[-1][3] - 8)
            r = map_rect(col, BREG, brect)
            spotlight(c, r, col_a * 0.8)
            glow(c, r, RED, col_a)
        if capk:
            overlay(c, capk, ct)
        return c

    f.fade_to(board_fr(0), 0.3)
    f.hold(lambda t: board_fr(t, capk="c4d", ct=(t - 0.5) / 0.4), 2.3)
    f.tween(lambda e: board_fr(9, e, "c4d", 1 - e), 0.5)
    f.hold(lambda t: board_fr(9, 1.0, "c4e", t / 0.4), 2.2)

    m = META["card"]
    card = _cap_img("card")
    cw, ch = m["w"], m["h"]
    stage = (30, 26, W - 60, H - 112)
    vh = cw * stage[3] / stage[2] * 0.62
    vw = vh * stage[2] / stage[3]
    over, start, stop = (0, 0, cw, cw * stage[3] / stage[2]), (0, 0, vw, vh), (0, min(ch * 0.15, ch - vh), vw, vh)

    def card_fr(region, ct):
        c = canvas()
        place(c, card, fit(region[2:], stage), css(region))
        overlay(c, "c4f", ct)
        return c

    f.fade_to(card_fr(over, 0), 0.3)
    f.hold(lambda t: card_fr(over, (t - 0.1) / 0.4), 0.7)
    f.tween(lambda e: card_fr(lerp(over, start, e), 1), 0.5)
    f.tween(lambda e: card_fr(lerp(start, stop, e), 1), 2.2)
    f.hold(lambda t: card_fr(stop, 1), 0.3)
    outro(f, "e4")
    return f


# ---- step 5: twins --------------------------------------------------------------------------------------------------
def define_step5():
    title("t5", 5, "Catch answers given from", "habit",
          "Every scene has a twin with one small change, so the right answer changes too. A model that is not really "
          "looking gives the same answer twice.", ["740 twin pairs", "one change each", "answer must flip"])
    label("l5o", "Original · answer V4, V7")
    label("l5t", "Twin · answer V4, V6")
    cap("c5a", "TWIN", "Outfall O moves to another stream: <b>0.64% of pixels</b> change, the answer flips.")
    cap("c5b", "ORIGINAL", 'Gemini 3.5 Flash: M1, M3. <span class="g">Right.</span>', "green")
    cap("c5c", "TWIN", 'Cooler water, key: none. Gemini: <b>M1, M3 again</b>. <span class="r">Wrong.</span>', "red")
    stamp("s5ok", True, "M1, M3 · right")
    stamp("s5bad", False, "M1, M3 · same answer")
    end("e5", "Step 5", "Right once is not enough.", "Both halves, or it's habit.",
        [('6 of 19', "pairs right on both halves, best model", "grad"), ("≤ 2 of 19", "every other model", ""),
         ("0 of 19", "open models", "r")],
        "yugesh1111.github.io/THIRSTMAP/#where")


def step5():
    f = Film()
    intro(f, "t5")
    a, b = img(PIPE / "8_original.jpg"), img(PIPE / "8_twin.jpg")
    h = 400
    wa = h * a.width / a.height
    ra, rb = (W / 2 - wa - 12, 30, wa, h), (W / 2 + 12, 30, wa, h)

    def pair_fr(t):
        c = canvas()
        ea, eb = kit.ease(t / 0.45), kit.ease((t - 0.7) / 0.45)
        place(c, a, (ra[0], ra[1] + (1 - ea) * 20, ra[2], ra[3]), alpha=ea)
        center_label(c, "l5o", ra[0] + ra[2] / 2, ra[1] + h + 8, ea)
        if eb > 0:
            place(c, b, (rb[0], rb[1] + (1 - eb) * 20, rb[2], rb[3]), alpha=eb)
            center_label(c, "l5t", rb[0] + rb[2] / 2, rb[1] + h + 8, eb)
            glow(c, rb, RED, kit.ease((t - 1.4) / 0.4) * 0.8)
        overlay(c, "c5a", (t - 1.4) / 0.4)
        return c
    f.fade_to(pair_fr(0), 0.35)
    f.hold(pair_fr, 3.6)

    o = img(ROOT / "docs/demo/analysis/level3_seed34416__Q8__thermal__gemini-3.5-flash.jpg")
    t_ = img(ROOT / "docs/demo/analysis/level3_seed34416_cf__Q8__thermal__gemini-3.5-flash.jpg")
    h = 452
    w = h * o.width / o.height
    big_o = (W / 2 - w / 2, 18, w, h)
    lo, rt = (W / 2 - w - 14, 18, w, h), (W / 2 + 14, 18, w, h)

    def gem_fr(phase, e=1.0, t=0.0):
        c = canvas()
        if phase == 0:                                      # original alone, verdict
            place(c, o, big_o)
            overlay(c, "s5ok", (t - 0.5) / 0.35, at=(big_o[0] + big_o[2] - 210, big_o[1] + 56), slide=10)
            overlay(c, "c5b", (t - 0.5) / 0.35)
        else:                                               # slide apart, twin arrives, verdict
            r1 = lerp(big_o, lo, e)
            place(c, o, r1)
            overlay(c, "s5ok", 1, at=(r1[0] + r1[2] - 210, r1[1] + 56), slide=0)
            if e > 0.2:
                place(c, t_, (rt[0] + (1 - e) * 60, rt[1], rt[2], rt[3]), alpha=e)
            if phase == 2:
                glow(c, rt, RED, kit.ease(t / 0.4))
                overlay(c, "s5bad", (t - 0.3) / 0.35, at=(rt[0] + rt[2] - 268, rt[1] + 56), slide=10)
                overlay(c, "c5c", (t - 0.3) / 0.35)
        return c
    f.fade_to(gem_fr(0), 0.4)
    f.hold(lambda t: gem_fr(0, t=t), 2.2)
    f.tween(lambda e: gem_fr(1, e), 0.6)
    f.hold(lambda t: gem_fr(2, t=t), 2.8)
    outro(f, "e5")
    return f


# ---- step 6: score your own model -----------------------------------------------------------------------------------
def define_step6():
    title("t6", 6, "Score", "your own model",
          "Download the questions, run any model, drop its replies on the leaderboard. Your browser scores them with "
          "the same rules and builds the same report card.", ["same rules", "same report card", "the file stays on your computer"])
    cap("c6a", "1", "Download the pack: the exact images, prompts and reply formats.")
    cap("c6b", "2", "Run any model. Save <b>one JSON line per reply</b>.")
    cap("c6c", "3", "Drop the file, or <b>try the sample</b>: Gemini 3.1 Flash-Lite's real replies.")
    cap("c6d", "YOURS", 'Scored on the page: <b class=a>48%</b> on 83 questions, ranked #2.', "amber")
    cap("c6e", "REPORT CARD", "The same card every model gets: skills, pairs, mistakes.", "amber")
    end("e6", "Step 6", "Bring your own model.", "Get the same report card.",
        [("1 file", "one JSON line per reply", "grad"), ("0 uploads", "scoring runs in your browser", ""),
         ("same", "rules, chance level and p-value", "")],
        "yugesh1111.github.io/THIRSTMAP/leaderboard/#yours")


def step6():
    f = Film()
    intro(f, "t6")
    m = META["lb_steps"]
    steps, sb = _cap_img("lb_steps"), m["boxes"]
    REG = (0, 0, m["w"], m["h"])
    rect = fit(REG[2:], (40, 90, W - 80, 300))
    sample = map_rect(sb["sample"][0], REG, rect)
    sx, sy = sample[0] + sample[2] / 2, sample[1] + sample[3] / 2

    def steps_fr(k, a, ck=None, ct=1.0, cur=None, click=0.0):
        c = canvas()
        place(c, steps, rect, css(REG))
        if k is not None:
            r = map_rect(sb["steps"][k], REG, rect)
            spotlight(c, r, a)
            glow(c, r, BLUE, a)
        if ck:
            overlay(c, ck, ct)
        if cur:
            cursor(c, *cur, click)
        return c

    f.fade_to(steps_fr(None, 0), 0.4)
    for k, ck in enumerate(("c6a", "c6b", "c6c")):
        f.tween(lambda e, k=k, ck=ck: steps_fr(k, e, ck, e), 0.4)
        f.hold(lambda t, k=k, ck=ck: steps_fr(k, 1, ck), 1.4 if k < 2 else 0.4)
    start = (sx + 160, sy + 120)
    f.tween(lambda e: steps_fr(2, 1, "c6c", 1, lerp(start, (sx, sy), e)), 0.7)
    f.tween(lambda e: steps_fr(2, 1, "c6c", 1, (sx, sy), e), 0.45)

    m = META["lb_yours_board"]
    board, yours = _cap_img("lb_yours_board"), m["boxes"]["yours"][0]
    BREG = (0, 0, m["w"], m["h"])
    brect = fit(BREG[2:], (30, 30, W - 60, H - 120))

    def board_fr(a, ct):
        c = canvas()
        place(c, board, brect, css(BREG))
        r = map_rect(yours, BREG, brect)
        spotlight(c, r, a * 0.7)
        glow(c, r, AMBER, a)
        overlay(c, "c6d", ct)
        return c
    f.fade_to(board_fr(0, 0), 0.35)
    f.tween(lambda e: board_fr(e, e), 0.5)
    f.hold(lambda t: board_fr(1, 1), 2.2)

    m = META["lb_yours_card"]
    card = _cap_img("lb_yours_card")
    cw, ch = m["w"], m["h"]
    stage = (30, 26, W - 60, H - 112)
    vh = cw * stage[3] / stage[2] * 0.62
    vw = vh * stage[2] / stage[3]
    over, a_, b_ = (0, 0, cw, cw * stage[3] / stage[2]), (0, 0, vw, vh), (0, min(ch * 0.2, ch - vh), vw, vh)

    def card_fr(region, ct):
        c = canvas()
        place(c, card, fit(region[2:], stage), css(region))
        overlay(c, "c6e", ct)
        return c
    f.fade_to(card_fr(over, 0), 0.35)
    f.hold(lambda t: card_fr(over, (t - 0.1) / 0.4), 0.7)
    f.tween(lambda e: card_fr(lerp(over, a_, e), 1), 0.5)
    f.tween(lambda e: card_fr(lerp(a_, b_, e), 1), 2.0)
    outro(f, "e6")
    return f


# ---- step 7: human test ---------------------------------------------------------------------------------------------
def define_step7():
    title("t7", 7, "Take the test", "yourself",
          "The same 32 questions the models answered, every before-and-after pair included. No sign-up; most people "
          "take 10 to 15 minutes.", ["32 questions", "7 pairs", "no sign-up"])
    cap("c7a", "TASK 1", "A thermal image. Which monitoring points are more than 3 °C too warm?")
    cap("c7b", "TICK", "Tick what you see, then <b>Next</b>.")
    cap("c7c", "TASK 2", "A topographic map. Which way does the stream flow below outfall O?")
    end("e7", "Step 7", "Can you trace the water", "better than the models?",
        [("32", "questions, the same ones the models got", "grad"), ("10–15 min", "most people", ""),
         ("6 of 19", "pairs: the best model's score to beat", "")],
        "yugesh1111.github.io/THIRSTMAP/human/")


def step7():
    f = Film()
    intro(f, "t7")
    m = META["human_1"]
    REG = (40, 200, 1120, 690)
    rect = fit(REG[2:], (30, 22, W - 60, H - 100))

    def at(box):
        r = map_rect(box, REG, rect)
        return r[0] + r[2] / 2, r[1] + r[3] / 2

    opt = at(m["boxes"]["opts"][2])
    nxt = at(META["human_1_ticked"]["boxes"]["next"][0])

    def fr(name, ck, ct=1.0, cur=None, click=0.0, region=REG):
        c = canvas()
        place(c, _cap_img(name), fit(region[2:], (30, 22, W - 60, H - 100)), css(region))
        if ck:
            overlay(c, ck, ct)
        if cur:
            cursor(c, *cur, click)
        return c

    start = (opt[0] - 140, opt[1] + 150)
    f.fade_to(fr("human_1", "c7a", 0), 0.4)
    f.hold(lambda t: fr("human_1", "c7a", t / 0.4, start), 1.8)
    f.tween(lambda e: fr("human_1", "c7a", 1, lerp(start, opt, e)), 0.6)
    f.tween(lambda e: fr("human_1" if e < 0.3 else "human_1_ticked", "c7b", 1, opt, e), 0.45)
    f.hold(lambda t: fr("human_1_ticked", "c7b", 1, opt), 0.6)
    f.tween(lambda e: fr("human_1_ticked", "c7b", 1, lerp(opt, nxt, e)), 0.6)
    f.tween(lambda e: fr("human_1_ticked", "c7b", 1, nxt, e), 0.4)
    f.fade_to(fr("human_2", "c7c", 0, nxt), 0.35)
    f.hold(lambda t: fr("human_2", "c7c", t / 0.4, nxt), 2.4)
    outro(f, "e7")
    return f


# ---- step 8: beyond right answers ----------------------------------------------------------------------------------
BEY = ROOT / "docs/demo/beyond"


def define_step8():
    t = json.loads((ROOT / "results/trace/summary.json").read_text())["models"]
    c = json.loads((ROOT / "results/cloud/summary.json").read_text())
    rw = sum(v["quadrants"]["right route, wrong villages"] for v in t.values())
    wr = sum(v["quadrants"]["wrong route, right villages"] for v in t.values())
    hid = [v["variants"]["hidden"] for v in c.values()]
    dec = [v["variants"]["decoy"] for v in c.values()]
    hn, made = sum(h["n"] for h in hid), sum(h["n"] - h["abstained"] for h in hid)
    dn, da = sum(d["n"] for d in dec), sum(d["abstained"] for d in dec)
    OV["t8"] = ('<div class="full" style="padding:140px 80px 0"><div class="kicker">ThirstMap · step 8 · new checks</div>'
                '<div class="big" style="margin-top:18px">Beyond right <span class="grad">answers</span></div>'
                '<div class="sub" style="margin-top:18px;max-width:700px">Is the reasoning right too? The model draws the '
                "water's route, scored cell by cell. And does it know when it cannot see?</div>"
                '<div class="row"><span class=pill>draw the route</span><span class=pill>scored cell by cell</span>'
                '<span class=pill>clouds that hide the answer</span></div></div>')
    label("l8a", "✓ Gemini 3.6 Flash: right route, wrong village")
    label("l8b", "✗ Qwen2.5-VL-3B: drawn the wrong way round")
    cap("c8a", "ROUTE", "The model draws the water's path; it is scored against the simulation, <b>cell by cell</b>.")
    cap("c8b", "REASONING", f'<b class=a>{rw}</b> replies followed the water but named the wrong villages; <b class=a>{wr}</b> named the right villages along a wrong route.', "amber")
    label("l8c", "Cloud hides the answer")
    label("l8d", "Under it: two exits fit every pixel")
    label("l8e", "Decoy: same cloud, answer visible")
    cap("c8c", "CAN'T TELL", f'Under a cloud that provably hides the answer, models made one up <span class="r">{made} of {hn}</span> times.', "red")
    cap("c8d", "DECOY", f"Same cloud where it does not matter: models abstained <b>{da} of {dn}</b> times. The test is fair.")


def step8():
    f = Film()
    intro(f, "t8")
    a, b = img(BEY / "trace/gemini-3.6-flash__level3_seed58561__satellite.jpg"), \
        img(BEY / "trace/Qwen2.5-VL-3B-Instruct__level3_seed58561__satellite.jpg")
    h = 380
    w = h * a.width / a.height
    ra, rb = (W / 2 - w - 14, 26, w, h), (W / 2 + 14, 26, w, h)

    def routes(t, ck):
        c = canvas()
        ea, eb = kit.ease(t / 0.45), kit.ease((t - 0.5) / 0.45)
        place(c, a, (ra[0], ra[1] + (1 - ea) * 20, w, h), alpha=ea)
        center_label(c, "l8a", ra[0] + w / 2, ra[1] + h + 8, ea)
        if eb > 0:
            place(c, b, (rb[0], rb[1] + (1 - eb) * 20, w, h), alpha=eb)
            center_label(c, "l8b", rb[0] + w / 2, rb[1] + h + 8, eb)
        glow(c, ra, GREEN, kit.ease((t - 1.1) / 0.4) * 0.8)
        glow(c, rb, RED, kit.ease((t - 1.1) / 0.4) * 0.8)
        overlay(c, ck, (t - 1.0) / 0.4 if ck == "c8a" else 1)
        return c
    f.fade_to(routes(0, "c8a"), 0.35)
    f.hold(lambda t: routes(t, "c8a"), 2.6)
    f.hold(lambda t: routes(9, "c8b"), 2.6)

    cl = img(BEY / "cloud/level1_seed91943.jpg")
    cw = 900
    chh = cw * cl.height / cl.width
    rc = (W / 2 - cw / 2, 60, cw, chh)
    third = cl.width / 3

    def cloud(t, ck):
        c = canvas()
        for k, key in enumerate(("l8c", "l8d", "l8e")):
            e = kit.ease((t - 0.55 * k) / 0.45)
            if e <= 0:
                continue
            r = (rc[0] + k * cw / 3 + 3, rc[1] + (1 - e) * 18, cw / 3 - 6, chh)
            place(c, cl, r, (k * third, 0, third, cl.height), alpha=e, radius=10)
            center_label(c, key, r[0] + r[2] / 2, rc[1] + chh + 10, e)
        glow(c, (rc[0] + 3, rc[1], cw / 3 - 6, chh), RED, kit.ease((t - 1.7) / 0.4) * 0.8)
        overlay(c, ck, (t - 1.6) / 0.4 if ck == "c8c" else 1)
        return c
    f.fade_to(cloud(0.2, "c8c"), 0.35)
    f.hold(lambda t: cloud(t + 0.2, "c8c"), 3.0)
    f.hold(lambda t: cloud(9, "c8d"), 2.4)
    outro(f, None)
    return f


NAMES = {0: "0_run_all_quick", 1: "1_how_a_task_is_made", 2: "2_variation", 3: "3_validation", 4: "4_results",
         5: "5_twins", 6: "6_score_your_model", 7: "7_human_test", 8: "8_beyond_right_answers"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("steps", nargs="*", type=int, default=list(NAMES))
    ap.add_argument("--quick-log", default="quick_log.json", help="timed output of run_all.sh --quick (step 0)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--no-overlays", action="store_true", help="reuse the rendered overlays")
    a = ap.parse_args()
    META.update(json.loads((CAP / "meta.json").read_text()))
    log = json.loads(Path(a.quick_log).read_text()) if 0 in a.steps else None
    lines = define_step0(log) if log else None
    for k in range(1, 9):
        globals()[f"define_step{k}"]()
    if not a.no_overlays:
        spec = CAP / "overlays.json"
        spec.write_text(json.dumps(OV))
        subprocess.run(["node", str(ROOT / "video/walkthrough/overlays.js"), str(spec), str(CAP)], check=True)
    for k in a.steps:
        film = step0(log, lines) if k == 0 else globals()[f"step{k}"]()
        film.save(Path(a.out) / f"{NAMES[k]}.gif")


if __name__ == "__main__":
    main()
