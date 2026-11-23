"""Satellite-style renderer: the same scene drawn as if seen from space.

No contour lines here. The AI has to read the terrain from relief shading,
follow channels (sandy riverbeds, dark seasonal streams, lines of riparian
vegetation) and use the annotations, as an analyst would with real imagery.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .terrain import CELL_M, L_KM, N, fractal, rc

S = 5                      # pixels per terrain cell
W = N * S                  # image size (800 px)
SS = 2                     # supersampling for the vector layers


def _up(a, resample=Image.BILINEAR):
    img = Image.fromarray(np.asarray(a, dtype=np.float32), mode="F")
    return np.asarray(img.resize((W, W), resample))


def _px(i, scale=1):
    r, c = rc(i)
    return ((c + 0.5) * S * scale, (r + 0.5) * S * scale)


def hillshade(z, azimuth=315.0, altitude=42.0, exag=2.5):
    dzdr, dzdc = np.gradient(z * exag, CELL_M / S)
    slope = np.arctan(np.hypot(dzdc, dzdr))
    aspect = np.arctan2(dzdr, -dzdc)
    az = math.radians(360.0 - azimuth + 90.0)
    zen = math.radians(90.0 - altitude)
    hs = math.cos(zen) * np.cos(slope) + math.sin(zen) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(hs, 0, 1)


def _font(size):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def _chaikin(pts, widths, rounds=2):
    for _ in range(rounds):
        if len(pts) < 3:
            break
        np_, nw = [pts[0]], [widths[0]]
        for (a, b), (wa, wb) in zip(zip(pts[:-1], pts[1:]), zip(widths[:-1], widths[1:])):
            np_ += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]),
                    (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
            nw += [0.75 * wa + 0.25 * wb, 0.25 * wa + 0.75 * wb]
        np_.append(pts[-1]); nw.append(widths[-1])
        pts, widths = np_, nw
    return pts, widths


def stream_polylines(s, P):
    """Split the stream network into head-to-junction polylines (cell index lists)."""
    stream, rec = s["stream"].ravel(), s["rec"]
    has_up = np.zeros(N * N, bool)
    for i in np.nonzero(stream)[0]:
        if rec[i] >= 0:
            has_up[rec[i]] = True
    heads = [i for i in np.nonzero(stream)[0] if not has_up[i]]
    heads.sort(key=lambda i: -s["acc"].flat[i])
    seen, lines = set(), []
    for h in heads:
        line, i = [int(h)], int(h)
        while rec[i] >= 0:
            i = int(rec[i])
            line.append(i)
            if i in seen or not stream[i] and s["lake"].flat[i]:
                break
            seen.add(i)
        seen.update(line[:-1])
        lines.append(line)
    return lines


def _channel_width(acc, P):
    return 1.8 + 3.0 * math.log10(acc / P["stream_cells"] + 1)   # px at 1x


def _parcels(rng, shape):
    """Crop-field mosaic: rotated grid of parcels with bunds."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    ang = rng.uniform(0, math.pi)
    u = xx * math.cos(ang) + yy * math.sin(ang)
    v = -xx * math.sin(ang) + yy * math.cos(ang)
    su, sv = rng.uniform(16, 26), rng.uniform(10, 18)
    iu, iv = np.floor(u / su), np.floor(v / sv)
    pid = (iu * 7919 + iv * 104729).astype(np.int64)
    palette = np.array([(112, 140, 72), (138, 150, 82), (176, 162, 104), (150, 120, 88),
                        (122, 102, 78), (96, 128, 66), (168, 150, 96)], float)
    col = palette[np.abs(pid) % len(palette)]
    bund = ((u % su) < 1.1) | ((v % sv) < 1.1)
    return col, bund


def render(s, p, nm, P, reveal=False, truth=None, title=None, season="dry", haze=0.0, coarse=1):
    """season: "dry" | "monsoon"; haze: 0-1 extra atmospheric haze; coarse: ground-resolution
    divisor (2 = half the resolution). Appearance only: the scene and its answers are unchanged."""
    rng = np.random.default_rng(s["seed"] + 77)
    disp = s["disp"]
    z_hi = _up(disp, Image.BICUBIC)
    hs = hillshade(z_hi)

    # ---- land cover, decided on the terrain grid then upsampled with ragged edges
    gr, gc = np.gradient(disp, CELL_M)
    slope = np.hypot(gr, gc)
    en = (disp - disp.min()) / (np.ptp(disp) + 1e-9)
    n1, n2 = fractal(rng, 2.6), fractal(rng, 3.2)
    forest = (slope > np.quantile(slope, 0.82)) | (n1 > 0.70)
    farm = (slope < np.quantile(slope, 0.40)) & (n2 > 0.50) & ~forest & (en < 0.85)
    scrub = (n1 > 0.52) & ~forest & ~farm
    hf = fractal(rng, 1.8, n=W)
    hf2 = fractal(rng, 2.4, n=W)
    def soften(m):
        m = m.astype(float)
        for _ in range(2):
            m = (m + np.roll(m, 1, 0) + np.roll(m, -1, 0) + np.roll(m, 1, 1) + np.roll(m, -1, 1)) / 5
        return m
    edge = lambda m: (_up(soften(m), Image.BICUBIC) + 0.45 * (hf - 0.5)) > 0.5
    F, A, SC = edge(forest), edge(farm), edge(scrub)
    LK = (_up(s["lake"].astype(float)) + 0.15 * (hf - 0.5)) > 0.5
    BUILT = np.zeros((W, W), bool)
    lc = (s.get("real") or {}).get("landcover")
    if lc is not None:                       # real ESA WorldCover classes
        cls = lambda *c: edge(np.isin(lc, c))
        F, A, SC, BUILT = cls(10, 95), cls(40), cls(20, 30, 90, 100), cls(50)
        LK = LK | cls(80)

    img = np.zeros((W, W, 3))
    img[:] = (176, 158, 120)
    img = img * (0.9 + 0.2 * hf2[..., None])                      # dry grass / soil
    speck = hf > 0.62
    img[speck] *= 0.92
    scrub_col = np.array((122, 124, 86)) * (0.85 + 0.3 * hf[..., None])
    img = np.where(SC[..., None], scrub_col, img)
    pcol, bund = _parcels(rng, (W, W))
    pcol = pcol * (0.92 + 0.16 * hf2[..., None])
    pcol[bund] *= 0.78
    img = np.where(A[..., None], pcol, img)
    canopy = np.where((hf > 0.5)[..., None], np.array((44, 62, 36)), np.array((70, 92, 52)))
    img = np.where(F[..., None], canopy * (0.9 + 0.2 * hf2[..., None]), img)
    if BUILT.any():                          # urban fabric: irregular blocks, mixed roofs, streets, trees
        yy, xx = np.mgrid[0:W, 0:W]
        wu = xx + 9 * (hf2 - 0.5)            # warp the grid so blocks are not perfectly regular
        wv = yy + 9 * (fractal(rng, 2.4, n=W) - 0.5)
        bw, bh = 13.0, 10.0
        bid = (np.floor(wu / bw) * 7919 + np.floor(wv / bh) * 104729).astype(np.int64)
        roofs = np.array([(168, 164, 156), (206, 204, 198), (150, 96, 74), (128, 126, 120),
                          (186, 178, 160), (92, 120, 160)], float)
        pick = np.abs(bid) % 100
        roof = roofs[np.select([pick < 34, pick < 56, pick < 74, pick < 88, pick < 97], [0, 1, 2, 3, 4], 5)]
        fine = fractal(rng, 1.2, n=W)
        footprint = fine > 0.42                                  # buildings vs courtyards inside a block
        urban = np.where(footprint[..., None], roof, np.array((132, 128, 118))) * (0.9 + 0.2 * hf[..., None])
        street = ((wu % bw) < 1.6) | ((wv % bh) < 1.6)
        urban[street] = (104, 102, 98)
        urban[(fine < 0.2) & ~street] = (64, 86, 52)             # street trees and small parks
        img = np.where(BUILT[..., None], urban, img)

    if season == "monsoon":                  # wet season: vegetation greens, soil darkens
        lum = img.mean(-1, keepdims=True)
        green = np.concatenate([0.62 * lum, 1.05 * lum + 10, 0.55 * lum], -1)
        img = 0.35 * img + 0.65 * green

    # ---- streams: polylines, supersampled for smooth edges
    lines = stream_polylines(s, P)
    big = W * SS
    rip = Image.new("L", (big, big), 0)
    bed = Image.new("L", (big, big), 0)
    wat = Image.new("L", (big, big), 0)
    dr, db, dw = ImageDraw.Draw(rip), ImageDraw.Draw(bed), ImageDraw.Draw(wat)
    for line in lines:
        pts = [_px(i, SS) for i in line]
        ws = [_channel_width(s["acc"].flat[i], P) * SS for i in line]
        if len(pts) > 4:
            xs = np.convolve(np.pad([q[0] for q in pts], 2, mode="edge"), np.ones(5) / 5, "valid")
            ys = np.convolve(np.pad([q[1] for q in pts], 2, mode="edge"), np.ones(5) / 5, "valid")
            pts = [pts[0]] + list(zip(xs[1:-1], ys[1:-1])) + [pts[-1]]
        pts, ws = _chaikin(pts, ws, rounds=3)
        for (a, b), w in zip(zip(pts[:-1], pts[1:]), ws[1:]):
            dr.line([a, b], fill=255, width=int(w * 2.5 + 9 * SS))
            db.line([a, b], fill=255, width=max(2, int(w + 1.5 * SS)))
            dw.line([a, b], fill=255, width=max(2, int(w)))
        for (x, y), w in zip(pts, ws):
            r = (w + 1.5 * SS) / 2
            db.ellipse([x - r, y - r, x + r, y + r], fill=255)
            dw.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=255)
    down = lambda im, blur: np.asarray(im.resize((W, W), Image.LANCZOS)
                                       .filter(ImageFilter.GaussianBlur(blur)), float) / 255
    RIP, BED, WAT = down(rip, 3.0), down(bed, 0.5), down(wat, 0.4)
    green = np.array((60, 92, 46)) * (0.85 + 0.3 * hf[..., None])
    img = img * (1 - 0.9 * RIP[..., None]) + green * 0.9 * RIP[..., None]
    img = img * (1 - BED[..., None]) + np.array((84, 88, 64)) * BED[..., None]      # wet banks
    img = img * (1 - WAT[..., None]) + np.array((46, 78, 88)) * WAT[..., None]      # water
    img = np.where(LK[..., None], np.array((52, 80, 88)) * (0.95 + 0.1 * hf2[..., None]), img)

    # ---- relief shading (how terrain is read without contours)
    img = img * (0.50 + 0.72 * hs[..., None])
    img = np.where(LK[..., None], np.array((50, 78, 86)), img)  # water is flat, unshaded

    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(base)

    # ---- villages: dirt patch + rooftops + a few trees
    roof_cols = [(172, 92, 62), (150, 150, 150), (214, 212, 204), (120, 70, 50), (72, 110, 168), (95, 85, 74)]
    for v in p["villages"]:
        cx, cy = _px(p["village_pos"][v])
        d.ellipse([cx - 17, cy - 13, cx + 17, cy + 13], fill=(184, 166, 132))
        for _ in range(int(rng.integers(18, 30))):
            a, r = rng.uniform(0, 2 * math.pi), rng.uniform(0, 14)
            x, y = cx + r * math.cos(a), cy + 0.8 * r * math.sin(a)
            w, h = rng.uniform(2.5, 5.5), rng.uniform(2.5, 4.5)
            if BED[min(W - 1, max(0, int(y))), min(W - 1, max(0, int(x)))] > 0.2:
                continue
            col = roof_cols[int(rng.choice(len(roof_cols), p=[.34, .26, .18, .1, .05, .07]))]
            d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=col)
        for _ in range(4):
            a, r = rng.uniform(0, 2 * math.pi), rng.uniform(6, 17)
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(52, 72, 40))

    # ---- data centre campus, pipe to outfall, treated-water pond
    sx, sy = _px(s["site"])
    ox, oy = _px(s["O"])
    d.line([sx, sy, ox, oy], fill=(204, 204, 198), width=2)
    d.rectangle([sx - 34, sy - 22, sx + 34, sy + 22], fill=(156, 156, 150))
    d.rectangle([sx - 30, sy - 18, sx + 6, sy + 2], fill=(230, 232, 234))
    d.rectangle([sx - 30, sy + 6, sx + 6, sy + 18], fill=(222, 224, 228))
    for k in range(6):
        d.rectangle([sx - 27 + 6 * k, sy - 15, sx - 24 + 6 * k, sy - 12], fill=(120, 124, 128))
    for k in range(4):
        tx, ty = sx + 15 + 9 * (k % 2), sy - 11 + 11 * (k // 2)
        d.ellipse([tx - 5, ty - 5, tx + 5, ty + 5], fill=(124, 126, 128))
        d.ellipse([tx - 3, ty - 3, tx + 3, ty + 3], fill=(58, 62, 66))
    for site in (p.get("siting") or {}).get("sites", []):     # cleared plots for proposed sites
        x, y = _px(site)
        d.rectangle([x - 15, y - 10, x + 15, y + 10], fill=(186, 168, 134))
    px_, py_ = _px(p["pond"])
    d.rectangle([px_ - 8, py_ - 6, px_ + 8, py_ + 6], fill=(170, 170, 164))
    d.rectangle([px_ - 6, py_ - 4, px_ + 6, py_ + 4], fill=(62, 98, 102))

    # ---- water stays on top of ground features (villages sit beside, not on, the channel)
    arr = np.asarray(base, float)
    water = np.array((46, 78, 88)) * (0.50 + 0.72 * hs[..., None])
    arr = arr * (1 - WAT[..., None]) + water * WAT[..., None]
    base = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # ---- sensor look: slight blur, grain, gentle haze
    arr = np.asarray(base.filter(ImageFilter.GaussianBlur(0.55)), float)
    arr = arr + rng.normal(0, 2.6, arr.shape)
    if haze:                                 # extra atmospheric haze lowers contrast
        h = 0.06 + 0.6 * haze
        arr = (1 - h) * arr + h * np.array((205, 210, 215))
    else:                                    # default look (kept bit-identical with the published dataset)
        arr = 0.94 * arr + 0.06 * np.array((205, 210, 215))
    base = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if coarse > 1:                           # coarser sensor: fewer ground pixels (labels stay crisp)
        base = base.resize((W // coarse, W // coarse), Image.BILINEAR).resize((W, W), Image.BILINEAR)
    base = base.convert("RGBA")

    # ---- annotation layer (labels an analyst would add)
    ann = Image.new("RGBA", base.size, (0, 0, 0, 0))
    a = ImageDraw.Draw(ann)
    f, fs = _font(15), _font(12)
    boxes = []

    STM = BED > 0.25

    def lbl(xy, t, font=f):
        a.text(xy, t, font=font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
        boxes.append((t, a.textbbox(xy, t, font=font, stroke_width=3)))

    def free(bb):
        x0, y0, x1, y1 = (int(v) for v in bb)
        if x0 < 2 or y0 < 2 or x1 > W - 2 or y1 > W - 2:
            return False
        if any(x0 < b[2] and b[0] < x1 and y0 < b[3] and b[1] < y1 for _, b in boxes):
            return False
        return STM[y0:y1, x0:x1].mean() < 0.01

    def place(ax_, ay_, t, offsets, font=f):
        for dx, dy in offsets:
            bb = a.textbbox((ax_ + dx, ay_ + dy), t, font=font, stroke_width=3)
            if free(bb):
                return lbl((ax_ + dx, ay_ + dy), t, font)
        lbl((ax_ + offsets[0][0], ay_ + offsets[0][1]), t, font)

    AROUND = [(12, -24), (12, 8), (-34, -24), (-34, 8), (-10, -36), (-10, 18), (22, -8), (-46, -8)]
    place(sx, sy, "DC-1", [(-30, -42), (-30, 26), (38, -10), (-80, -10)])
    a.ellipse([ox - 6, oy - 6, ox + 6, oy + 6], fill=(255, 140, 20, 255), outline=(0, 0, 0, 255), width=2)
    place(ox, oy, "O", [(-22, -8), (9, -8), (-6, -27), (-6, 9)])
    place(px_, py_, "P", [(10, -2), (-20, -2), (-4, 8), (-4, -20)], fs)
    for v, name in nm["village"].items():
        cx, cy = _px(p["village_pos"][v])
        place(cx, cy, name, AROUND)
    for w_, name in nm["wetland"].items():
        cx, cy = _px(w_)
        hexa = [(cx + 11 * math.cos(math.pi / 3 * k), cy + 11 * math.sin(math.pi / 3 * k)) for k in range(6)]
        a.polygon(hexa, outline=(235, 80, 235, 255), width=3)
        place(cx, cy, name, [(12, -20), (12, 4), (-24, -20), (-24, 4), (-5, -32), (-5, 13)], fs)

    sit = p.get("siting")
    if sit:
        for site, o in zip(sit["sites"], sit["site_outfalls"]):
            x, y = _px(site)
            ox_, oy_ = _px(o)
            n = max(2, int(math.hypot(ox_ - x, oy_ - y) / 6))
            for k in range(0, n, 2):                       # dashed planned pipe
                t0, t1 = k / n, min(1, (k + 1) / n)
                a.line([x + (ox_ - x) * t0, y + (oy_ - y) * t0, x + (ox_ - x) * t1, y + (oy_ - y) * t1],
                       fill=(255, 90, 90, 255), width=2)
            a.rectangle([x - 16, y - 11, x + 16, y + 11], outline=(255, 90, 90, 255), width=3)
            a.ellipse([ox_ - 5, oy_ - 5, ox_ + 5, oy_ + 5], fill=(255, 255, 255, 255), outline=(200, 30, 30, 255), width=2)
            place(x, y, nm["site"][site], [(-12, -34), (-12, 14), (20, -9), (-46, -9)])
            if reveal and site == sit["clean_site"]:
                a.ellipse([x - 26, y - 26, x + 26, y + 26], outline=(40, 230, 60, 255), width=4)
    itk = p.get("intake")
    if itk:
        ix, iy = _px(itk["intake"])
        a.polygon([(ix - 8, iy - 7), (ix + 8, iy - 7), (ix, iy + 7)], fill=(40, 110, 255, 255),
                  outline=(255, 255, 255, 255))
        place(ix, iy, "I", [(9, -20), (9, 2), (-18, -20), (-18, 2)])
        if reveal:
            for v in itk["upstream"]:
                cx, cy = _px(p["village_pos"][v])
                a.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline=(60, 140, 255, 255), width=4)

    if reveal and truth:
        path_pts = [_px(i) for i in s["path"]]
        a.line(path_pts, fill=(255, 40, 40, 200), width=5, joint="curve")
        for v in p["villages"]:
            cx, cy = _px(p["village_pos"][v])
            col = (255, 40, 40, 255) if v in truth["hit"] else (190, 190, 190, 255)
            a.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], outline=col, width=4)
        if p.get("good") is not None:
            gx, gy = _px(p["good"])
            a.ellipse([gx - 18, gy - 18, gx + 18, gy + 18], outline=(40, 230, 60, 255), width=4)

    # scale bar (1 km) + north arrow
    km_px = W / L_KM
    a.rectangle([W - 32 - km_px - 8, W - 40, W - 24, W - 12], fill=(0, 0, 0, 150))
    a.line([W - 28 - km_px, W - 18, W - 28, W - 18], fill=(255, 255, 255, 255), width=4)
    lbl((W - 28 - km_px / 2 - 16, W - 40), "1 km", fs)
    a.polygon([(W - 30, 14), (W - 38, 34), (W - 22, 34)], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    lbl((W - 36, 36), "N", fs)

    out = Image.alpha_composite(base, ann).convert("RGB")
    bar = 30
    framed = Image.new("RGB", (W, W + bar), (22, 24, 28))
    framed.paste(out, (0, bar))
    ImageDraw.Draw(framed).text((8, 7), title or "", font=_font(13), fill=(235, 235, 235))
    framed.info["labels"] = [(t, (x0, y0 + bar, x1, y1 + bar)) for t, (x0, y0, x1, y1) in boxes
                             if t not in ("1 km", "N")]
    framed.info["offset"] = bar
    return framed
