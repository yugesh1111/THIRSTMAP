"""Show how one task is made: a single scene followed through every pipeline step.

Rebuilds the scene from its seed, then draws one panel per step:
  1 terrain          2 water simulation     3 scene script (placements + traps)
  4 answer key       5 independent check    6 three image styles
  7 pixel evidence   8 counterfactual twin  (9 scoring is drawn by the demo page from real replies)
and writes docs/pipeline/steps.json with the numbers each caption quotes.

Usage: python3 pipeline_visuals.py --dataset dataset --scene level4_seed48947 --out docs/pipeline
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from thirstmap import render_sat
from thirstmap.questions import answer_key
from thirstmap.scene import make
from thirstmap.terrain import CELL_M, N, params, rc, trace
from thirstmap.validate import _water_like, independent_answers, pysheds_routing
from verify_results import recover_jobs

K = 4                                   # panel pixels per terrain cell (160 cells -> 640 px)
SIDE = N * K
# one-hue ramps (light -> dark) for magnitude; status colours only for agree / disagree
ORANGE = [(251, 227, 214), (240, 160, 120), (217, 89, 38), (138, 58, 20)]
BLUE = {100: (205, 226, 251), 250: (134, 182, 239), 450: (42, 120, 214), 650: (16, 66, 129)}
PATH = (235, 104, 52)                   # categorical slot 2: the wastewater
INK, GREY = (11, 11, 11), (120, 119, 114)
GOOD, CRIT = (12, 163, 12), (208, 59, 59)
AQUA, VIOLET = (27, 175, 122), (98, 80, 214)


def font(size, bold=False):
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)


def ramp(t, stops):
    t = np.clip(t, 0, 1) * (len(stops) - 1)
    i = np.minimum(t.astype(int), len(stops) - 2)
    f = (t - i)[..., None]
    a, b = np.array(stops, float)[i], np.array(stops, float)[i + 1]
    return a + (b - a) * f


def shade(z):
    gy, gx = np.gradient(z * 2.5, CELL_M)
    slope, aspect = np.arctan(np.hypot(gx, gy)), np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(42)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(hs, 0, 1)


def up(rgb):
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize((SIDE, SIDE), Image.NEAREST)


def xy(i):
    r, c = rc(i)
    return (c + 0.5) * K, (r + 0.5) * K


def base_grey(s):
    hs = shade(s["disp"])
    g = 228 + 22 * (hs - 0.5)
    rgb = np.stack([g, g, g * 0.985], -1)
    return rgb


def streams(rgb, s, strong=False):
    rgb = rgb.copy()
    rgb[s["lake"]] = BLUE[100]
    rgb[s["stream"]] = BLUE[250] if not strong else BLUE[450]
    rgb[s["main"] & ~s["lake"]] = BLUE[450] if not strong else BLUE[650]
    return rgb


def marker(d, i, label, fill, shape="circle", r=7, ring=None, text=INK, edge=(255, 255, 255)):
    x, y = xy(i)
    box = (x - r, y - r, x + r, y + r)
    if shape == "square":
        d.rectangle(box, fill=fill, outline=(255, 255, 255), width=2)
    elif shape == "triangle":
        d.polygon([(x, y - r - 1), (x - r, y + r - 1), (x + r, y + r - 1)], fill=fill, outline=(255, 255, 255))
    else:
        d.ellipse(box, fill=fill, outline=edge, width=2)
    if ring:
        d.ellipse((x - r - 5, y - r - 5, x + r + 5, y + r + 5), outline=ring, width=3)
    if label:
        f = font(15, True)
        w = d.textlength(label, font=f)
        tx = x + r + 4 if x + r + 6 + w < SIDE else x - r - 4 - w
        d.text((tx + 1, y - 9 + 1), label, font=f, fill=(255, 255, 255))
        d.text((tx, y - 9), label, font=f, fill=text)


def polyline(d, cells, colour, width):
    pts = [xy(i) for i in cells]
    d.line(pts, fill=colour, width=width, joint="curve")


def rebuild(key):
    P = params(key["level"])
    for k, _ in recover_jobs(key):
        s, p = make(key["seed"], P, bi=k)
        qs, nm, truth = answer_key(s, p)
        got = {q["id"]: q["answer"] for q in qs}
        if all(got.get(q["id"]) == q["answer"] for q in key["questions"]):
            return s, p, qs, nm, truth, P
    raise RuntimeError("could not rebuild the scene from its seed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--scene", default="level4_seed48947")
    ap.add_argument("--out", default="docs/pipeline")
    a = ap.parse_args()
    ds, out = Path(a.dataset), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    folder = ds / "scenes" / a.scene
    key = json.loads((folder / "answer_key.json").read_text())
    s, p, qs, nm, truth, P = rebuild(key)
    q1 = next(q for q in qs if q["id"] == "Q1")
    vname = nm["village"]
    facts = dict(scene=a.scene, level=key["level"], seed=key["seed"], size_km=N * CELL_M / 1000,
                 cells=N, cell_m=CELL_M)

    # 1 terrain
    z = s["disp"]
    t = (z - z.min()) / (z.max() - z.min())
    rgb = ramp(t, ORANGE) * (0.62 + 0.38 * shade(z))[..., None]
    up(rgb).save(out / "1_terrain.png", optimize=True)
    facts["elev_min_m"], facts["elev_max_m"] = round(float(z.min())), round(float(z.max()))

    # 2 water simulation: flow accumulation (log), lakes from depression filling
    acc = s["acc"].reshape(N, N)
    la = np.log10(acc)
    t = np.clip((la - 1.0) / (la.max() - 1.0), 0, 1)
    rgb = base_grey(s)
    blue = ramp(t, [BLUE[100], BLUE[250], BLUE[450], BLUE[650]])
    alpha = np.clip((la - 1.2) / 1.2, 0, 1)[..., None]
    rgb = rgb * (1 - alpha) + blue * alpha
    rgb[s["lake"]] = BLUE[250]
    up(rgb).save(out / "2_water.png", optimize=True)
    facts["stream_cells"] = int(s["stream"].sum())
    facts["lake_cells"] = int(s["lake"].sum())
    facts["max_upstream_km2"] = round(float(acc.max()) * CELL_M * CELL_M / 1e6, 1)

    # 3 scene script
    im = up(streams(base_grey(s), s))
    d = ImageDraw.Draw(im)
    traps = {v: "upstream, same stream" for v in p["trap_up"]}
    traps.update({v: "close, other stream" for v in p["trap_near"]})
    for w in p["wet"]:
        marker(d, w, nm["wetland"][w], AQUA, "square", r=6)
    for v in p["villages"]:
        marker(d, p["village_pos"][v], vname[v], (255, 255, 255) if v not in traps else (250, 178, 25),
               r=7, edge=INK)
    marker(d, s["site"], "DC-1", INK, "square", r=9)
    marker(d, s["O"], "O", PATH, r=7)
    if p.get("intake"):
        marker(d, p["intake"]["intake"], "I", BLUE[450], "triangle", r=7)
    im.save(out / "3_scene.png", optimize=True)
    facts["villages"] = sorted(vname[v] for v in p["villages"])
    facts["traps"] = {vname[v]: why for v, why in traps.items()}
    facts["wetlands"] = sorted(nm["wetland"][w] for w in p["wet"])

    # 4 answer key: trace downstream from the outfall
    im = up(streams(base_grey(s), s))
    d = ImageDraw.Draw(im)
    hit = set(v for v in p["villages"] if v in set(s["path"]))
    last = max(s["path"].index(v) for v in hit)
    polyline(d, s["path"][: last + 12], PATH, 6)
    for v in p["villages"]:
        if v in hit:
            marker(d, p["village_pos"][v], vname[v], PATH, r=8, ring=PATH)
        else:
            marker(d, p["village_pos"][v], vname[v], (245, 245, 242), r=6, text=GREY, edge=GREY)
    marker(d, s["O"], "O", INK, r=7)
    im.save(out / "4_answer.png", optimize=True)
    facts["answer"] = q1["answer"]
    facts["path_cells"] = last + 1
    facts["question"] = q1["question"]

    # 5 independent check with pysheds
    rec2, _ = pysheds_routing(s["filled"], s.get("outlet", "south"))
    agree = (rec2 == s["rec"]).reshape(N, N)
    rgb = base_grey(s) * 0.25 + np.array([236, 235, 231]) * 0.75
    rgb[~agree] = CRIT
    im = up(rgb)
    d = ImageDraw.Draw(im)
    path2 = trace(rec2, s["O"])
    polyline(d, path2[: last + 12], BLUE[450], 6)
    polyline(d, s["path"][: last + 12], PATH, 2)
    for v in hit:
        marker(d, p["village_pos"][v], vname[v], PATH, r=7)
    im.save(out / "5_check.png", optimize=True)
    ind, agree_frac = independent_answers(s, p, nm, qs)
    same = {q["id"]: ind.get(q["id"]) == q["answer"] for q in qs if q["id"] in ind}
    facts["pysheds_agree_pct"] = round(100 * agree_frac, 2)
    facts["pysheds_disagree_cells"] = int((~agree).sum())
    facts["answers_identical"] = f"{sum(same.values())}/{len(same)}"
    facts["same_path"] = path2[: last + 1] == s["path"][: last + 1]

    # 6 three styles (exactly the dataset images)
    for style in ("satellite", "map", "thermal"):
        src = folder / f"{style}.png"
        if src.exists():
            Image.open(src).convert("RGB").save(out / f"6_{style}.jpg", quality=86)

    # 7 pixel evidence on the satellite image the model sees
    sat = Image.open(folder / "satellite.png").convert("RGB")
    tag = f"Region TM-{s['seed']:05d} | difficulty {key['level']}/5 | {N * CELL_M / 1000:.0f} km x {N * CELL_M / 1000:.0f} km"
    again = render_sat.render(s, p, nm, P, title=f"{tag} | satellite-style | {s['drain_note'].lower()}")
    off = again.info["offset"]
    arr = np.asarray(sat)
    facts["satellite_rebuilt_identical"] = bool(np.array_equal(np.asarray(again.convert("RGB")), arr))
    im = sat.copy()
    d = ImageDraw.Draw(im)
    ok = 0
    cells = s["path"][: last + 1]
    for i in cells:
        x, y = render_sat._px(i)
        y += off
        x, y = int(round(x)), int(round(y))
        good = _water_like("satellite", arr[max(0, y - 5):y + 6, max(0, x - 5):x + 6])
        ok += good
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=GOOD if good else CRIT, outline=(255, 255, 255))
    im.save(out / "7_pixels.jpg", quality=88)
    facts["pixel_cells"] = len(cells)
    facts["pixel_visible_pct"] = round(100 * ok / len(cells), 1)

    # 8 counterfactual twin: only the changed pixels are highlighted
    twin = ds / "scenes" / f"{a.scene}_cf"
    if twin.exists():
        tk = json.loads((twin / "answer_key.json").read_text())
        b = np.asarray(Image.open(folder / "satellite.png").convert("RGB")).astype(int)
        c = np.asarray(Image.open(twin / "satellite.png").convert("RGB")).astype(int)
        diff = np.abs(b - c).sum(-1) > 0
        hi = c.copy()
        dil = diff.copy()
        for _ in range(3):
            dil = dil | np.roll(dil, 1, 0) | np.roll(dil, -1, 0) | np.roll(dil, 1, 1) | np.roll(dil, -1, 1)
        hi[dil & ~diff] = (232, 64, 140)
        Image.fromarray(hi.astype(np.uint8)).save(out / "8_twin.jpg", quality=88)
        Image.open(folder / "satellite.png").convert("RGB").save(out / "8_original.jpg", quality=88)
        facts["twin_change"] = tk.get("cf_change")
        facts["twin_answer"] = next(q["answer"] for q in tk["questions"] if q["id"] == "Q1")
        facts["twin_pixels_changed_pct"] = round(100 * float(diff.mean()), 2)
    (out / "steps.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(facts, indent=1, default=str))


if __name__ == "__main__":
    main()
