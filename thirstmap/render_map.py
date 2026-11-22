"""Topographic-map renderer: hillshade, contour lines, streams and symbols."""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LightSource, LinearSegmentedColormap
from matplotlib.patches import Rectangle

from .terrain import CELL_M, L_KM, N, km

TINT = LinearSegmentedColormap.from_list(
    "tint", [(.56, .68, .46), (.74, .73, .52), (.72, .60, .44), (.86, .80, .70)])


def render(s, p, nm, P, reveal=False, truth=None, title=""):
    disp = s["disp"]
    fig, ax = plt.subplots(figsize=(8.6, 8.6), dpi=100)
    fig.subplots_adjust(left=.02, right=.98, bottom=.05, top=.95)
    rgb = LightSource(azdeg=315, altdeg=40).shade(
        disp, cmap=TINT, blend_mode="soft", vert_exag=4, dx=CELL_M, dy=CELL_M)
    ax.imshow(rgb, extent=(0, L_KM, L_KM, 0))
    lake_rgba = np.zeros((N, N, 4))
    lake_rgba[s["lake"]] = (.36, .58, .80, .95)
    ax.imshow(lake_rgba, extent=(0, L_KM, L_KM, 0))

    X, Y = np.meshgrid((np.arange(N) + .5) * CELL_M / 1000, (np.arange(N) + .5) * CELL_M / 1000)
    ci = P["contour_m"]
    levels = np.arange(math.floor(disp.min() / ci) * ci, disp.max() + ci, ci)
    idx = [lv for lv in levels if lv % (5 * ci) == 0]
    ax.contour(X, Y, disp, levels=levels, colors=[(.45, .32, .2)], linewidths=.35, alpha=.8)
    cs = ax.contour(X, Y, disp, levels=idx, colors=[(.4, .27, .16)], linewidths=.9)
    ax.clabel(cs, fmt="%d m", fontsize=6.5, inline=True)
    n_contour_texts = len(ax.texts)

    segs, widths = [], []
    for i in np.nonzero(s["stream"].ravel())[0]:
        r = s["rec"][i]
        if r >= 0:
            segs.append([km(i), km(r)])
            widths.append(.6 + 2.2 * math.log10(s["acc"].flat[i] / P["stream_cells"] + 1))
    ax.add_collection(LineCollection(segs, colors=[(.16, .40, .72)], linewidths=widths, capstyle="round"))

    if reveal:
        ax.plot(*zip(*[km(i) for i in s["path"]]), color=(.9, .1, .1), lw=3.2, alpha=.8, zorder=4)

    sx, sy = km(s["site"])
    ax.add_patch(Rectangle((sx - .08, sy - .05), .16, .10, fc=(.55, .57, .6), ec="k", lw=.8, zorder=5))
    for dx in (-.045, 0, .045):
        ax.add_patch(plt.Circle((sx + dx, sy), .017, fc="white", ec="k", lw=.5, zorder=6))
    ax.text(sx, sy - .09, "DC-1  AI data centre", ha="center", fontsize=7.5, weight="bold", zorder=7,
            bbox=dict(fc="white", ec="none", alpha=.75, pad=1))
    ox, oy = km(s["O"])
    ax.plot([sx, ox], [sy, oy], ls="--", color="k", lw=1, zorder=5)
    ax.plot(ox, oy, "o", ms=7, mfc=(.95, .55, .1), mec="k", zorder=7)
    ax.text(ox - .1, oy + .02, "O", fontsize=9, weight="bold", zorder=7)

    px, py = km(p["pond"])
    ax.plot(px, py, "o", ms=9, mfc=(.3, .6, .9), mec="k", zorder=7)
    ax.text(px + .06, py + .03, f"P  {disp.flat[p['pond']]:.0f} m", fontsize=7.5, weight="bold", zorder=7,
            bbox=dict(fc="white", ec="none", alpha=.75, pad=1))

    for f, name in nm["farm"].items():
        fx, fy = km(f)
        ax.add_patch(Rectangle((fx - .06, fy - .04), .12, .08, fc=(.80, .78, .35), ec="k", lw=.6,
                               zorder=5, hatch="////"))
        ax.text(fx, fy - .07, name, ha="center", fontsize=7.5, weight="bold", zorder=7)
        if reveal and truth:
            ok = name in truth["lower"]
            ax.text(fx + .09, fy + .02, "✓" if ok else "✗", color="green" if ok else "red",
                    fontsize=13, weight="bold", zorder=8)

    for v, name in nm["village"].items():
        vx, vy = km(p["village_pos"][v])
        ax.plot(vx, vy, "s", ms=7, mfc=(.15, .15, .15), mec="white", zorder=7)
        ax.text(vx + .05, vy - .05, name, fontsize=8, weight="bold", zorder=7,
                bbox=dict(fc="white", ec="none", alpha=.75, pad=1))
        if reveal and truth:
            ax.plot(vx, vy, "o", ms=17, mfc="none", mec="red" if v in truth["hit"] else "grey",
                    mew=2, zorder=8)

    for w, name in nm["wetland"].items():
        wx, wy = km(w)
        ax.plot(wx, wy, "h", ms=11, mfc=(.55, .25, .65), mec="white", zorder=7)
        ax.text(wx, wy + .015, name, ha="center", va="center", fontsize=7, color="white",
                weight="bold", zorder=8)
        if reveal and w == p["good"]:
            ax.plot(wx, wy, "o", ms=20, mfc="none", mec=(0, .75, 0), mew=2.5, zorder=8)

    sit = p.get("siting")
    if sit:
        red = (.55, .05, .05)
        for site, o in zip(sit["sites"], sit["site_outfalls"]):
            x, y = km(site)
            ox, oy = km(o)
            ax.plot([x, ox], [y, oy], ls=(0, (3, 2)), color=red, lw=1.1, zorder=5)
            ax.add_patch(Rectangle((x - .05, y - .035), .10, .07, fc="none", ec=red, lw=1.6, ls="--", zorder=6))
            ax.plot(ox, oy, "o", ms=5, mfc="white", mec=red, zorder=7)
            ax.text(x, y - .06, nm["site"][site], ha="center", fontsize=8, weight="bold", color=red, zorder=7,
                    bbox=dict(fc="white", ec="none", alpha=.75, pad=1))
            if reveal and site == sit["clean_site"]:
                ax.plot(x, y, "o", ms=24, mfc="none", mec=(0, .75, 0), mew=2.5, zorder=8)
    itk = p.get("intake")
    if itk:
        ix, iy = km(itk["intake"])
        ax.plot(ix, iy, "v", ms=10, mfc=(.1, .3, .9), mec="white", zorder=7)
        ax.text(ix + .05, iy - .06, "I", fontsize=9, weight="bold", color=(.1, .2, .7), zorder=7,
                bbox=dict(fc="white", ec="none", alpha=.75, pad=1))
        if reveal:
            for v in itk["upstream"]:
                vx, vy = km(p["village_pos"][v])
                ax.plot(vx, vy, "o", ms=22, mfc="none", mec=(.1, .3, .95), mew=2, zorder=8)

    ax.plot([L_KM - 1.25, L_KM - .25], [L_KM - .15] * 2, color="k", lw=3)
    ax.text(L_KM - .75, L_KM - .2, "1 km", ha="center", fontsize=8, weight="bold")
    ax.annotate("N", xy=(L_KM - .2, .12), xytext=(L_KM - .2, .42), ha="center", fontsize=10,
                weight="bold", arrowprops=dict(arrowstyle="-|>", color="k", lw=1.5))
    ax.set_xlim(0, L_KM)
    ax.set_ylim(L_KM, 0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=9, loc="left")
    fig.text(.02, .015, "■ village   ⬢ wetland site   ▨ farm   ● P treated-water pond   ● O outfall   "
             f"contour interval {ci} m", fontsize=7.5)
    fig.canvas.draw()
    rend, H = fig.canvas.get_renderer(), fig.bbox.height

    def px(i):
        X, Y = ax.transData.transform(km(i))
        return X, H - Y

    labels = []
    for t in ax.texts[n_contour_texts:]:
        if t.get_text() in ("✓", "✗", "1 km", "N"):
            continue
        e = t.get_window_extent(rend)
        labels.append((t.get_text(), (e.x0, H - e.y1, e.x1, H - e.y0)))
    fig.tm_px, fig.tm_labels = px, labels
    return fig
