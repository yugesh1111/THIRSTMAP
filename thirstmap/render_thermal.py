"""Thermal false-colour renderer: how much warmer than normal the water is.

Land is shown in muted grey (as in thermal products); every stream and lake
is coloured by its water-temperature excess on a fixed 0-12 deg C scale with
a legend. Warm cooling water from outfall O cools and mixes as it flows.
"""
from collections import deque

import matplotlib
import numpy as np
from PIL import Image, ImageDraw

from .render_sat import SS, W, _font, _px, _up, hillshade, stream_polylines
from .terrain import L_KM, N, fractal

VMAX = 15.0
CMAP = matplotlib.colormaps["inferno"]


def colour(dt):
    r, g, b, _ = CMAP(0.06 + 0.94 * min(max(dt, 0.0), VMAX) / VMAX)
    return int(r * 255), int(g * 255), int(b * 255)


def _smooth(pts, attrs, rounds=3):
    for _ in range(rounds):
        if len(pts) < 3:
            break
        npts, nat = [pts[0]], [[a[0]] for a in attrs]
        for k in range(len(pts) - 1):
            (ax, ay), (bx, by) = pts[k], pts[k + 1]
            npts += [(.75 * ax + .25 * bx, .75 * ay + .25 * by), (.25 * ax + .75 * bx, .25 * ay + .75 * by)]
            for j, a in enumerate(attrs):
                nat[j] += [.75 * a[k] + .25 * a[k + 1], .25 * a[k] + .75 * a[k + 1]]
        npts.append(pts[-1])
        for j, a in enumerate(attrs):
            nat[j].append(a[-1])
        pts, attrs = npts, nat
    return pts, attrs


def lake_values(s, dT):
    """Each lake takes the temperature excess at the point where the plume leaves it."""
    lake = s["lake"].ravel()
    comp = -np.ones(N * N, int)
    vals = {}
    for start in np.nonzero(lake)[0]:
        if comp[start] >= 0:
            continue
        cid = len(vals)
        q = deque([start]); comp[start] = cid
        while q:
            i = q.popleft()
            r, c = divmod(int(i), N)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    j = rr * N + cc
                    if 0 <= rr < N and 0 <= cc < N and lake[j] and comp[j] < 0:
                        comp[j] = cid; q.append(j)
        vals[cid] = 0.0
    for i in s["path"]:
        if lake[i]:
            vals[comp[i]] = dT[i]          # last path cell inside the lake wins (exit value)
    return comp.reshape(N, N), vals


def render(s, p, nm, P, reveal=False, truth=None, title="", reserve=False):
    rng = np.random.default_rng(s["seed"] + 91)
    dT = p["plume"]["dT"]
    hs = hillshade(_up(s["disp"], Image.BICUBIC))
    noise = fractal(rng, 2.2, n=W)
    land = 62 + 62 * hs + 18 * (noise - .5)
    img = np.stack([land * .92, land * .95, land * 1.0], -1)

    comp, vals = lake_values(s, dT)
    for cid, v in vals.items():
        m = _up((comp == cid).astype(float)) > 0.5
        img[m] = colour(v)
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

    big = Image.new("RGB", (W * SS, W * SS))
    big.paste(base.resize((W * SS, W * SS)))
    d = ImageDraw.Draw(big)
    for line in stream_polylines(s, P):
        pts = [_px(i, SS) for i in line]
        ws = [max(4.0, 1.4 * (1.8 + 3.0 * np.log10(s["acc"].flat[i] / P["stream_cells"] + 1))) * SS
              for i in line]
        vs = [dT.get(i, 0.0) for i in line]
        pts, (ws, vs) = _smooth(pts, [ws, vs])
        for k in range(len(pts) - 1):
            d.line([pts[k], pts[k + 1]], fill=colour(vs[k + 1]), width=int(ws[k + 1]))
            x, y, r = pts[k + 1][0], pts[k + 1][1], ws[k + 1] / 2
            d.ellipse([x - r, y - r, x + r, y + r], fill=colour(vs[k + 1]))
    out = big.resize((W, W), Image.LANCZOS).convert("RGBA")

    ann = Image.new("RGBA", out.size, (0, 0, 0, 0))
    a = ImageDraw.Draw(ann)
    f, fs = _font(15), _font(12)
    boxes = []
    # drawn over the map later (colour legend, scale bar, north arrow): labels must not sit there (check V10b)
    km_px_ = W / L_KM
    RESERVED = [(6, W - 88, 286, W - 22), (W - 32 - km_px_ - 8, W - 40, W - 24, W - 12), (W - 40, 12, W - 20, 54)]
    if reserve:
        boxes += [("+legend", RESERVED[0]), ("1 km", RESERVED[1]), ("N", RESERVED[2])]

    def lbl(xy, t, font=f, col=(255, 255, 255, 255)):
        a.text(xy, t, font=font, fill=col, stroke_width=3, stroke_fill=(0, 0, 0, 255))
        boxes.append((t, a.textbbox(xy, t, font=font, stroke_width=3)))
    sx, sy = _px(s["site"])
    a.rectangle([sx - 30, sy - 18, sx + 30, sy + 18], fill=(236, 236, 236, 255), outline=(0, 0, 0, 255))
    lbl((sx - 30, sy - 40), "DC-1")
    ox, oy = _px(s["O"])
    a.ellipse([ox - 6, oy - 6, ox + 6, oy + 6], outline=(255, 255, 255, 255), width=3)
    lbl((ox - 22, oy - 8), "O")
    for v, name in nm["village"].items():
        cx, cy = _px(p["village_pos"][v])
        a.rectangle([cx - 5, cy - 5, cx + 5, cy + 5], fill=(30, 220, 230, 255), outline=(0, 0, 0, 255))
        lbl((cx + 9, cy - 22), name)
    for m, name in nm["monitor"].items():           # water-quality monitoring points
        cx, cy = _px(m)
        a.polygon([(cx, cy - 9), (cx + 9, cy), (cx, cy + 9), (cx - 9, cy)], outline=(255, 255, 255, 255), width=3)
        lbl((cx + 11, cy - 22), name)
        if reveal:
            t = p["plume"]["point_dT"][m]
            a.ellipse([cx - 20, cy - 20, cx + 20, cy + 20],
                      outline=(255, 50, 50, 255) if t > 3.0 else (200, 200, 200, 255), width=4)
            lbl((cx + 11, cy + 2), f"+{t:.1f}°C", fs)

    # legend: colour bar 0-12 deg C
    x0, y0, bw, bh = 14, W - 62, 260, 14
    a.rectangle([x0 - 8, y0 - 26, x0 + bw + 12, y0 + bh + 26], fill=(0, 0, 0, 170))
    for k in range(bw):
        a.line([x0 + k, y0, x0 + k, y0 + bh], fill=colour(VMAX * k / (bw - 1)) + (255,))
    for t in range(0, int(VMAX) + 1, 3):
        x = x0 + (bw - 1) * t / VMAX
        a.line([x, y0 + bh, x, y0 + bh + 4], fill=(255, 255, 255, 255), width=2)
        a.text((x - 4, y0 + bh + 5), str(t), font=fs, fill=(255, 255, 255, 255))
    a.text((x0, y0 - 22), "Water temperature above normal (°C)", font=fs, fill=(255, 255, 255, 255))

    km_px = W / L_KM
    a.rectangle([W - 32 - km_px - 8, W - 40, W - 24, W - 12], fill=(0, 0, 0, 150))
    a.line([W - 28 - km_px, W - 18, W - 28, W - 18], fill=(255, 255, 255, 255), width=4)
    lbl((W - 28 - km_px / 2 - 16, W - 40), "1 km", fs)
    a.polygon([(W - 30, 14), (W - 38, 34), (W - 22, 34)], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    lbl((W - 36, 36), "N", fs)

    res = Image.alpha_composite(out, ann).convert("RGB")
    bar = 30
    framed = Image.new("RGB", (W, W + bar), (22, 24, 28))
    framed.paste(res, (0, bar))
    ImageDraw.Draw(framed).text((8, 7), title, font=_font(13), fill=(235, 235, 235))
    framed.info["labels"] = [(t, (x0, y0 + bar, x1, y1 + bar)) for t, (x0, y0, x1, y1) in boxes
                             if t not in ("1 km", "N") and not t.startswith("+")]
    framed.info["offset"] = bar
    framed.info["reserved"] = [(x0, y0 + bar, x1, y1 + bar) for x0, y0, x1, y1 in RESERVED]
    return framed
