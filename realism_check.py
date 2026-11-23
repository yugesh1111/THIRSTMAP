"""Do the simulated streams on real terrain run where real water is?

For each real-terrain location, the pipeline's own flow simulation (priority-flood + D8 on Copernicus DEM
GLO-30) is compared with ESA WorldCover 2021 surface water (class 80, permanent water bodies) on the same
4 x 4 km window and 25 m grid. Metric: the share of real-water cells within 50 m of a simulated stream or lake,
against the share of ALL cells within 50 m of one (what random placement would give). Lift > 1 means the
simulated drainage follows real water more than chance.

Writes docs/REALISM.md and docs/realism.png.   Usage: python3 realism_check.py
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from thirstmap import realterrain
from thirstmap.terrain import CELL_M, N, accumulate, d8_receivers, params, priority_flood

WATER = 80                        # ESA WorldCover: permanent water bodies


def near(mask, r):
    out = mask.copy()
    for _ in range(r):
        out = out | np.roll(out, 1, 0) | np.roll(out, -1, 0) | np.roll(out, 1, 1) | np.roll(out, -1, 1)
    return out


def main():
    P = params(3)
    rows, panels = [], []
    for name in realterrain.LOCATIONS:
        R = realterrain.load(name)
        z = R["z"].astype(float)
        filled = priority_flood(z, "all")
        lake = (filled - z) > 2.5
        acc = accumulate(filled, d8_receivers(filled, "all")).reshape(N, N)
        sim = (acc >= P["stream_cells"]) | lake
        water = R["landcover"] == WATER
        zone = near(sim, 2)                                   # within 50 m (2 cells of 25 m)
        if water.sum() == 0:
            rows.append((R["desc"], 0, None, None, None))
            continue
        hit = (water & zone).sum() / water.sum()
        base = zone.mean()
        rows.append((R["desc"], int(water.sum()), hit, base, hit / base))
        # panel: real water (blue) and simulated streams (orange) on a light ground
        rgb = np.full((N, N, 3), 238, np.uint8)
        rgb[water] = (42, 120, 214)
        rgb[sim & ~water] = (217, 89, 38)
        rgb[sim & water] = (20, 60, 120)
        panels.append((name, Image.fromarray(rgb).resize((320, 320), Image.NEAREST)))
    f = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
    sheet = Image.new("RGB", (len(panels) * 332 + 12, 372), (243, 245, 242))
    for k, (name, im) in enumerate(panels):
        sheet.paste(im, (12 + k * 332, 40))
        ImageDraw.Draw(sheet).text((12 + k * 332, 12), name.replace("_", " ").title(), font=f, fill=(15, 34, 48))
    sheet.save("docs/realism.png", optimize=True)
    L = ["# Realism check: simulated streams vs real water", "",
         "On real terrain the pipeline simulates drainage from the Copernicus DEM. Here that simulation is compared "
         "with ESA WorldCover 2021 permanent water (class 80) on the same 4 × 4 km window and 25 m grid. "
         "*Near* = within 50 m of a simulated stream or lake. *Chance* = share of all cells near one, i.e. what "
         "real water would score if the simulated network were placed at random. Lift = near / chance.", "",
         "| Location | Real-water cells | Near a simulated stream or lake | Chance | Lift |", "|---|---|---|---|---|"]
    for desc, n, hit, base, lift in rows:
        L.append(f"| {desc} | {n} | {'–' if hit is None else f'{100 * hit:.0f}%'} | "
                 f"{'–' if base is None else f'{100 * base:.0f}%'} | {'–' if lift is None else f'{lift:.1f}×'} |")
    enough = [r for r in rows if r[1] >= 30 and r[4] is not None]
    few = [r[0].split(" (")[0] for r in rows if r[1] < 30]
    if enough:
        L += ["", f"**Where a window holds at least 30 real-water cells ({len(enough)} of {len(rows)} locations), the "
              f"real water lies within 50 m of the simulated drainage {min(r[4] for r in enough):.1f}× to "
              f"{max(r[4] for r in enough):.1f}× as often as random placement would give.**"
              + (f" {', '.join(few)}: too little mapped open water to judge." if few else "")]
    L += ["", "![simulated streams (orange) and real water (blue); dark blue = both](realism.png)", "",
          "Limits: WorldCover maps open water at 10 m, so small streams and drains are often absent from it, and the "
          "DEM is a surface model (buildings and trees included), lightly smoothed. Facilities and villages in "
          "real-terrain scenes are hypothetical; only the land and its drainage are real."]
    open("docs/REALISM.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L[5:5 + len(rows) + 1]))


if __name__ == "__main__":
    main()
