"""Shared building blocks for the README walkthrough GIFs (see steps.py).

A Film is a list of 960x540 frames drawn with PIL on a dark backdrop: real page captures and dataset images placed
with a moving camera, a spotlight and glow on the part that matters, and text overlays rendered by overlays.js in the
site's fonts. Film.save() encodes an 800x450 GIF with ffmpeg.
"""
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H, FPS, S = 960, 540, 10, 2                  # canvas, frame rate, overlay/capture scale (deviceScaleFactor)
OUT_W, OUT_H = 800, 450
BLUE, RED, GREEN, AMBER = (90, 167, 255), (255, 122, 122), (70, 208, 122), (240, 165, 75)
OVERLAYS = Path("video/build/walkthrough")      # set by steps.py


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    if isinstance(a, (int, float)):
        return a + (b - a) * t
    return tuple(x + (y - x) * t for x, y in zip(a, b))


@lru_cache(None)
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


def canvas():
    return background().convert("RGBA")


@lru_cache(None)
def img(path):
    return Image.open(path).convert("RGB")


@lru_cache(None)
def ov(name):
    o = Image.open(OVERLAYS / f"ov_{name}.png").convert("RGBA")
    return o.resize((o.width // S, o.height // S), Image.LANCZOS)


def fit(wh, box):
    """Rect for an item of size wh letterboxed (contained) in box (x, y, w, h)."""
    bx, by, bw, bh = box
    k = min(bw / wh[0], bh / wh[1])
    w, h = wh[0] * k, wh[1] * k
    return (bx + (bw - w) / 2, by + (bh - h) / 2, w, h)


def map_rect(r, region, rect):
    """Rect r given in the source image's coordinates -> canvas, for `region` of the image shown in `rect`."""
    k = rect[2] / region[2]
    return (rect[0] + (r[0] - region[0]) * k, rect[1] + (r[1] - region[1]) * k, r[2] * k, r[3] * k)


def shadow(c, rect, radius=14, strength=150):
    x, y, w, h = (round(v) for v in rect)
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle((x, y + 10, x + w, y + h + 10), radius, fill=strength)
    c.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(18)))


def place(c, im, rect, region=None, radius=14, alpha=1.0, shade=True, border=True):
    """Draw `region` (x, y, w, h in im's pixels; default all of it) of image `im` into canvas `rect`."""
    if alpha <= 0:
        return
    region = region or (0, 0, im.width, im.height)
    x, y, w, h = region
    fx, fy, fw, fh = (round(v) for v in rect)
    if fw < 2 or fh < 2:
        return
    if shade:
        shadow(c, rect, radius, int(150 * alpha))
    crop = im.crop((round(x), round(y), round(x + w), round(y + h))).resize((fw, fh), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (fw, fh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, fw - 1, fh - 1), radius, fill=int(255 * alpha))
    c.paste(crop, (fx, fy), mask)
    if border:
        line = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(line).rounded_rectangle((fx, fy, fx + fw - 1, fy + fh - 1), radius,
                                               outline=(255, 255, 255, int(28 * alpha)), width=1)
        c.alpha_composite(line)


def spotlight(c, rect, alpha, radius=12, depth=150):
    if alpha <= 0:
        return
    x, y, w, h = (round(v) for v in rect)
    m = Image.new("L", (W, H), int(depth * alpha))
    ImageDraw.Draw(m).rounded_rectangle((x - 4, y - 4, x + w + 4, y + h + 4), radius, fill=0)
    c.paste(Image.new("RGBA", (W, H), (6, 9, 11, 255)), (0, 0), m.filter(ImageFilter.GaussianBlur(3)))


def glow(c, rect, color=BLUE, alpha=1.0, radius=12):
    if alpha <= 0:
        return
    x, y, w, h = (round(v) for v in rect)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((x - 3, y - 3, x + w + 3, y + h + 3), radius,
                                            outline=color + (int(255 * alpha),), width=6)
    c.alpha_composite(layer.filter(ImageFilter.GaussianBlur(9)))
    sharp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sharp).rounded_rectangle((x - 2, y - 2, x + w + 2, y + h + 2), radius,
                                            outline=color + (int(235 * alpha),), width=2)
    c.alpha_composite(sharp)


def overlay(c, name, t, at="bottom", slide=18):
    """Fade and slide in overlay `name`; t in [0, 1] is its entry progress (values > 1 are clamped).
    at: 'bottom' (centred caption), 'full' (a 960x540 layer), 'center', or an (x, y) top-left."""
    if t <= 0:
        return
    o = ov(name).copy()
    e = ease(t)
    if at == "bottom":
        x, y = (W - o.width) // 2, H - o.height - 24
    elif at == "full":
        x, y = 0, 0
    elif at == "center":
        x, y = (W - o.width) // 2, (H - o.height) // 2
    else:
        x, y = at
    o.putalpha(o.getchannel("A").point(lambda v: int(v * e)))
    c.alpha_composite(o, (round(x), round(y + (1 - e) * slide)))


def cursor(c, x, y, click=0.0):
    """A pointer at (x, y); click in (0, 1) draws an expanding ripple."""
    if 0 < click < 1:
        r = 8 + 26 * click
        ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((x - r, y - r, x + r, y + r), outline=BLUE + (int(255 * (1 - click)),), width=3)
        c.alpha_composite(ring)
    pts = [(0, 0), (0, 22), (6, 16.5), (10, 26), (14, 24.5), (10, 15.5), (17.5, 15.5)]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.polygon([(x + px + 1.5, y + py + 2) for px, py in pts], fill=(0, 0, 0, 120))
    layer = layer.filter(ImageFilter.GaussianBlur(1.5))
    d = ImageDraw.Draw(layer)
    d.polygon([(x + px, y + py) for px, py in pts], fill=(255, 255, 255, 255), outline=(10, 10, 10, 255))
    c.alpha_composite(layer)


class Film:
    def __init__(self):
        self.frames = []

    def emit(self, c):
        self.frames.append(c.convert("RGB"))

    def hold(self, build, seconds):
        """build(t) -> canvas, t = seconds since the start of this hold."""
        for i in range(max(1, round(seconds * FPS))):
            self.emit(build(i / FPS))

    def tween(self, build, seconds):
        """build(e) -> canvas, e eased from just above 0 to 1."""
        n = max(1, round(seconds * FPS))
        for i in range(1, n + 1):
            self.emit(build(ease(i / n)))

    def fade_to(self, c, seconds=0.4):
        a, b = self.frames[-1], c.convert("RGB")
        n = max(1, round(seconds * FPS))
        for i in range(1, n + 1):
            self.frames.append(Image.blend(a, b, ease(i / n)))

    def save(self, out, colors=128):
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            for i, f in enumerate(self.frames):
                f.save(f"{tmp}/{i:04d}.png")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", f"{tmp}/%04d.png",
                            "-vf", f"scale={OUT_W}:{OUT_H}:flags=lanczos,split[a][b];"
                            f"[a]palettegen=max_colors={colors}:stats_mode=full[p];"
                            "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                            "-loop", "0", str(out)], check=True)
        print(f"{out}: {len(self.frames)} frames, {len(self.frames) / FPS:.1f} s, {out.stat().st_size / 1e6:.1f} MB")
