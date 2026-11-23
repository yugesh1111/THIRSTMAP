"""Animated GIFs for the README: groups of related images played as a loop.

  styles.gif         one scene: satellite -> topographic map -> thermal -> answer key
  difficulty.gif     the difficulty dial, level 1 -> 5
  counterfactual.gif original -> twin (one small change flips the answer), with answer keys
  appearance.gif     one scene in dry season -> monsoon -> haze -> coarse sensor (answers unchanged)
  real_terrain.gif   real terrain in Navi Mumbai, Hyderabad, Pune and Chennai

Usage: python3 make_gifs.py --dataset dataset --out docs/gifs
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIDE = 520


def frame(path, caption, sub=""):
    im = Image.open(path).convert("RGB")
    im = im.crop((0, 30, im.width, im.height)) if im.height > im.width else im      # drop the title bar
    im.thumbnail((SIDE, SIDE), Image.LANCZOS)
    canvas = Image.new("RGB", (SIDE, SIDE + 62), (22, 24, 28))
    canvas.paste(im, ((SIDE - im.width) // 2, 62))
    d = ImageDraw.Draw(canvas)
    d.text((12, 8), caption, font=ImageFont.truetype("DejaVuSans-Bold.ttf", 19), fill=(245, 245, 245))
    d.text((12, 36), sub, font=ImageFont.truetype("DejaVuSans.ttf", 14), fill=(200, 200, 200))
    return canvas


def save(frames, path, ms=1600):
    pal = [f.quantize(colors=200, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=ms, loop=0, optimize=True)
    print(f"{path}  {path.stat().st_size // 1024} KB, {len(frames)} frames")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--out", default="docs/gifs")
    a = ap.parse_args()
    ds, out = Path(a.dataset), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sc = ds / "scenes"
    full = [p for p in sorted(sc.glob("level3_seed*")) if not p.name.endswith("_cf") and (p / "thermal.png").exists()]
    s = full[0]
    save([frame(s / "satellite.png", "Satellite-style image", "what the AI sees: terrain from shading, streams, labels"),
          frame(s / "map.png", "Topographic map", "same scene, same answer key: contours and symbols"),
          frame(s / "thermal.png", "Thermal image", "same scene: warm cooling water spreading from outfall O"),
          frame(s / "satellite_reveal.png", "Answer key (from the water simulation)",
                "red: where the wastewater goes · rings: affected villages")], out / "styles.gif")

    lv = [next(p for p in sorted(sc.glob(f"level{k}_seed*")) if not p.name.endswith("_cf")) for k in range(1, 6)]
    save([frame(p / "map.png", f"Difficulty {k}/5", "rougher terrain, more streams and villages as the level rises")
          for k, p in enumerate(lv, 1)], out / "difficulty.gif", ms=1300)

    twin = next(p for p in sorted(sc.glob("level*_cf"))
                if json.loads((p / "answer_key.json").read_text())["cf_kind"] == "outfall")
    key = json.loads((twin / "answer_key.json").read_text())
    orig = sc / key["pair_of"]
    q1 = {q["id"]: q["answer"] for q in json.loads((orig / "answer_key.json").read_text())["questions"]}
    q1t = {q["id"]: q["answer"] for q in key["questions"]}
    save([frame(orig / "satellite.png", "Original", "Which villages receive DC-1's wastewater?"),
          frame(orig / "satellite_reveal.png", f"Original: answer {', '.join(q1.get('Q1', []))}", "answer key"),
          frame(twin / "satellite.png", "Counterfactual twin", "only change: the pipe now ends on another stream"),
          frame(twin / "satellite_reveal.png", f"Twin: answer {', '.join(q1t.get('Q1', []))}",
                "the answer MUST change; a model that does not look keeps the old one")], out / "counterfactual.gif")

    vdir = ds / "variants"
    if vdir.exists():
        v = sorted(vdir.iterdir())[5]
        save([frame(sc / v.name / "satellite.png", "Dry season (original)", "same scene, same answers in all four looks"),
              frame(v / "monsoon.png", "Monsoon", "wet season: greener vegetation"),
              frame(v / "haze.png", "Haze", "dust / smog lowers contrast"),
              frame(v / "coarse.png", "Coarse sensor", "half the ground resolution")], out / "appearance.gif", ms=1300)

    cities = {"navi_mumbai": "Navi Mumbai", "hyderabad": "Hyderabad", "pune": "Pune", "chennai": "Chennai"}
    fr = []
    for loc, name in cities.items():
        p = next((p for p in sorted(sc.glob(f"real_{loc}_seed*")) if not p.name.endswith("_cf")), None)
        if p:
            fr.append(frame(p / "satellite.png", f"Real terrain: {name}",
                            "Copernicus elevation + ESA land cover; facility is hypothetical"))
    if fr:
        save(fr, out / "real_terrain.gif", ms=1500)


if __name__ == "__main__":
    main()
