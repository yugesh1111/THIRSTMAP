"""Compose the README step 4 GIF (docs/gifs/walkthrough/4_results.gif) from real page captures.

    node video/step4/capture.js http://127.0.0.1:8799 video/build/step4   # docs/ served locally
    node video/step4/overlays.js video/build/step4
    python video/step4/compose.py video/build/step4 docs/gifs/walkthrough/4_results.gif

Everything on screen is a capture of the real demo page and leaderboard (dark theme); the camera moves, the dimming,
the glow and the captions are added here. Numbers in the captions are the ones the pages show.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H, FPS, S = 960, 540, 10, 2          # output size, frame rate, capture scale (deviceScaleFactor)
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "video/build/step4")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/gifs/walkthrough/4_results.gif")
META = json.loads((SRC / "meta.json").read_text())
IMG = {k: Image.open(SRC / f"{k}.png").convert("RGB") for k in ("found", "board", "card")}
OV = {p.stem[3:]: Image.open(p).convert("RGBA") for p in SRC.glob("ov_*.png")}
BLUE, RED = (90, 167, 255), (255, 122, 122)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def background():
    bg = Image.new("RGB", (W, H), (11, 15, 18))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse((-260, -320, 520, 300), fill=(20, 52, 92))
    d.ellipse((560, 260, 1260, 860), fill=(14, 60, 52))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    bg = Image.blend(bg, glow, 0.55)
    d = ImageDraw.Draw(bg)
    for x in range(0, W, 40):
        d.line((x, 0, x, H), fill=(19, 25, 29))
    for y in range(0, H, 40):
        d.line((0, y, W, y), fill=(19, 25, 29))
    return bg


BG = background()


def shoot(name, region, frame_rect, radius=14):
    """Paste `region` (x, y, w, h in CSS px of capture `name`) into `frame_rect` (x, y, w, h on the canvas)."""
    x, y, w, h = region
    fx, fy, fw, fh = (round(v) for v in frame_rect)
    crop = IMG[name].crop((round(x * S), round(y * S), round((x + w) * S), round((y + h) * S)))
    crop = crop.resize((fw, fh), Image.LANCZOS)
    mask = Image.new("L", (fw, fh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, fw - 1, fh - 1), radius, fill=255)
    return crop, mask, (fx, fy)


def card_shadow(canvas, rect, radius=14, strength=150):
    x, y, w, h = (round(v) for v in rect)
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle((x, y + 10, x + w, y + h + 10), radius, fill=strength)
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    canvas.paste((0, 0, 0), (0, 0), sh)


def glow_box(canvas, rect, color=BLUE, alpha=1.0, radius=12):
    if alpha <= 0:
        return
    x, y, w, h = (round(v) for v in rect)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x - 3, y - 3, x + w + 3, y + h + 3), radius, outline=color + (int(255 * alpha),), width=6)
    blur = layer.filter(ImageFilter.GaussianBlur(9))
    canvas.alpha_composite(blur)
    sharp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sharp).rounded_rectangle((x - 2, y - 2, x + w + 2, y + h + 2), radius, outline=color + (int(235 * alpha),), width=2)
    canvas.alpha_composite(sharp)


def spotlight(canvas, rect, alpha, radius=12):
    """Dim everything except `rect`."""
    if alpha <= 0:
        return
    x, y, w, h = (round(v) for v in rect)
    m = Image.new("L", (W, H), int(150 * alpha))
    ImageDraw.Draw(m).rounded_rectangle((x - 4, y - 4, x + w + 4, y + h + 4), radius, fill=0)
    m = m.filter(ImageFilter.GaussianBlur(3))
    canvas.paste(Image.new("RGBA", (W, H), (6, 9, 11, 255)), (0, 0), m)


def overlay(canvas, name, t, anchor="bottom", dy=0):
    """Fade and slide in overlay `name` (rendered at 2x); t in [0, 1] is its entry progress."""
    if t <= 0:
        return
    ov = OV[name]
    ov = ov.resize((ov.width // S, ov.height // S), Image.LANCZOS)
    e = ease(t)
    if anchor == "bottom":
        pos = ((W - ov.width) // 2, round(H - ov.height - 26 + (1 - e) * 18) + dy)
    else:
        pos = (0, round((1 - e) * 22) + dy)
    a = ov.getchannel("A").point(lambda v: int(v * e))
    ov.putalpha(a)
    canvas.alpha_composite(ov, pos)


def cam_rect(region, box):
    """Canvas rect for showing `region` letterboxed into `box` (x, y, w, h), keeping aspect."""
    bx, by, bw, bh = box
    k = min(bw / region[2], bh / region[3])
    w, h = region[2] * k, region[3] * k
    return (bx + (bw - w) / 2, by + (bh - h) / 2, w, h), k


def to_canvas(r, region, frame):
    k = frame[2] / region[2]
    return (frame[0] + (r[0] - region[0]) * k, frame[1] + (r[1] - region[1]) * k, r[2] * k, r[3] * k)


frames = []


def emit(c):
    frames.append(c.convert("RGB"))


def hold(build, seconds):
    for i in range(round(seconds * FPS)):
        emit(build(i / FPS))


def crossfade(a, b, seconds):
    n = round(seconds * FPS)
    for i in range(1, n + 1):
        frames.append(Image.blend(a, b, ease(i / n)))


# ---- 1. title -------------------------------------------------------------------------------------------------------
def title(t):
    c = BG.convert("RGBA")
    overlay(c, "title", t / 0.7, anchor="top")
    return c


hold(title, 1.9)

# ---- 2. "What we found" cards: zoom to each in turn ----------------------------------------------------------------
fw, fh = META["found"]["w"], META["found"]["h"]
cards = META["found"]["boxes"]["cards"]
FULL = (0, 0, fw, fh)
STAGE = (40, 40, W - 80, H - 150)


def found_frame(region, active=None, act_a=0.0, cap=None, cap_t=0.0):
    c = BG.convert("RGBA")
    rect, _ = cam_rect(region, STAGE)
    card_shadow(c, rect)
    crop, mask, pos = shoot("found", region, rect)
    c.paste(crop, pos, mask)
    if active is not None:
        r = to_canvas(cards[active], region, rect)
        spotlight(c, r, act_a)
        glow_box(c, r, RED if active == 2 else BLUE, act_a)
    if cap:
        overlay(c, cap, cap_t)
    return c


def focus(k):
    x, y, w, h = cards[k]
    pad_x, pad_y = 150, 60
    reg = (max(0, x - pad_x), max(0, y - pad_y), w + 2 * pad_x, h + 2 * pad_y)
    if reg[0] + reg[2] > fw:
        reg = (fw - reg[2], reg[1], reg[2], reg[3])
    reg = (reg[0], reg[1], reg[2], min(reg[3], fh - reg[1]))
    return reg


crossfade(frames[-1], found_frame(FULL).convert("RGB"), 0.4)
hold(lambda t: found_frame(FULL), 0.3)
prev = FULL
for k, cap in zip((0, 1, 2), ("cap1", "cap2", "cap3")):
    tgt = focus(k)
    n = round(0.5 * FPS)
    for i in range(1, n + 1):
        e = ease(i / n)
        emit(found_frame(lerp(prev, tgt, e), k, e))
    hold(lambda t, k=k, tgt=tgt, cap=cap: found_frame(tgt, k, 1.0, cap, t / 0.4), 1.7)
    prev = tgt
n = round(0.5 * FPS)
for i in range(1, n + 1):
    e = ease(i / n)
    emit(found_frame(lerp(prev, FULL, e), 2, 1 - e))
hold(lambda t: found_frame(FULL), 0.2)

# ---- 3. leaderboard: rows arrive, then the pairs column lights up ----------------------------------------------------
bw, bh = META["board"]["w"], META["board"]["h"]
rows = META["board"]["boxes"]["rows"]
heads = META["board"]["boxes"]["heads"]
BREG = (0, 0, bw, bh)
BSTAGE = (30, 34, W - 60, H - 130)
brect, _ = cam_rect(BREG, BSTAGE)
head_h = rows[0][1]


def board_frame(t_rows, col_a=0.0, cap=None, cap_t=0.0):
    c = BG.convert("RGBA")
    card_shadow(c, brect)
    crop, mask, pos = shoot("board", BREG, brect)
    shown = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    k = brect[2] / bw
    hh = round(head_h * k)
    shown.paste(crop.crop((0, 0, crop.width, hh)), (0, 0))
    for i, r in enumerate(rows):
        e = ease((t_rows - 0.13 * i) / 0.4)
        if e <= 0:
            continue
        y0, y1 = round(r[1] * k), round((r[1] + r[3]) * k)
        strip = crop.crop((0, y0, crop.width, min(y1 + 1, crop.height))).convert("RGBA")
        strip.putalpha(int(255 * e))
        shown.alpha_composite(strip, (round((1 - e) * 40), y0))
    frame_bg = Image.new("RGBA", crop.size, (22, 28, 32, 255))
    frame_bg.alpha_composite(shown)
    c.paste(frame_bg, pos, mask)
    if col_a > 0:
        hx, _, hw, _ = heads[5]
        col = (hx - 6, 4, hw + 12, rows[-1][1] + rows[-1][3] - 8)
        r = to_canvas(col, BREG, brect)
        spotlight(c, r, col_a * 0.8)
        glow_box(c, r, RED, col_a)
    if cap:
        overlay(c, cap, cap_t)
    return c


crossfade(frames[-1], board_frame(0).convert("RGB"), 0.3)
hold(lambda t: board_frame(t, cap="cap4", cap_t=(t - 0.5) / 0.4), 2.3)
n = round(0.5 * FPS)
for i in range(1, n + 1):
    emit(board_frame(9, ease(i / n), "cap4", 1 - ease(i / n)))
hold(lambda t: board_frame(9, 1.0, "cap5", t / 0.4), 2.2)

# ---- 4. report card: a slow camera move down the real card ----------------------------------------------------------
cw, ch = META["card"]["w"], META["card"]["h"]
CSTAGE = (30, 26, W - 60, H - 112)
view_h = cw * CSTAGE[3] / CSTAGE[2] * 0.62        # zoomed in: 62% of the card's width fills the stage
view_w = view_h * CSTAGE[2] / CSTAGE[3]
start = (0, 0, view_w, view_h)
end = (0, min(ch * 0.15, ch - view_h), view_w, view_h)      # straight down to the before-and-after pairs
over = (0, 0, cw, cw * CSTAGE[3] / CSTAGE[2])


def card_frame(region, cap_t):
    c = BG.convert("RGBA")
    rect, _ = cam_rect(region, CSTAGE)
    card_shadow(c, rect)
    crop, mask, pos = shoot("card", region, rect)
    c.paste(crop, pos, mask)
    overlay(c, "cap6", cap_t)
    return c


crossfade(frames[-1], card_frame(over, 0).convert("RGB"), 0.3)
hold(lambda t: card_frame(over, (t - 0.1) / 0.4), 0.7)
n = round(0.5 * FPS)
for i in range(1, n + 1):
    emit(card_frame(lerp(over, start, ease(i / n)), 1))
n = round(2.2 * FPS)
for i in range(1, n + 1):
    emit(card_frame(lerp(start, end, ease(i / n)), 1))
hold(lambda t: card_frame(end, 1), 0.3)

# ---- 5. end card --------------------------------------------------------------------------------------------------
def end_card(t):
    c = BG.convert("RGBA")
    overlay(c, "end", t / 0.6, anchor="top")
    return c


crossfade(frames[-1], end_card(1).convert("RGB"), 0.4)
hold(lambda t: end_card(1), 2.6)

# ---- encode ---------------------------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    for i, f in enumerate(frames):
        f.save(f"{tmp}/{i:04d}.png")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", f"{tmp}/%04d.png", "-vf",
                    "scale=800:450:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];"
                    "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", "-loop", "0", str(OUT)], check=True)
print(f"{len(frames)} frames, {len(frames) / FPS:.1f} s -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
