"""Where did each model send the water? Error overlays, consequence stories and a mechanism test.

For the frontier check (results/frontier) and the main run (results/models):
  * overlays: the model's answer drawn on the image it saw, beside the true water path
    (green = right pick, red = wrong pick, amber = missed), one per frontier task for the best API model;
  * pair figures: original | twin for each before-and-after pair, per model;
  * stories: what each wrong answer would mean on the ground (a village left unwarned, a site wrongly approved);
  * mechanism: are wrong villages the ones NEAREST the outfall (distance instead of flow), and are the first
    villages on the path caught more often than later ones?
Every scene is rebuilt from its seed and checked against its stored answer key (thermap.rebuild).

Usage: python3 overlays.py --dataset dataset --out results/analysis
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from thirstmap import realterrain, render_map  # noqa: E402
from thirstmap.rebuild import label_cells, rebuild  # noqa: E402
from thirstmap.render_sat import _px  # noqa: E402
from thirstmap.scoring import score  # noqa: E402
from thirstmap.terrain import CELL_M, N, dist, trace  # noqa: E402

PATH, RIGHT, WRONG, MISSED, INK, PAPER = (24, 200, 235), (22, 163, 74), (220, 38, 38), (245, 158, 11), (15, 34, 48), (243, 245, 242)
LABEL_Q = {"Q1", "Q2", "Q3", "Q4", "Q6", "Q7", "Q8"}          # answers that are labels drawn on the image


def font(size, bold=True):
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)


def short(m):
    return m.split(":", 1)[-1].split("@")[0].split("/")[-1].replace("-Instruct", "")


def as_set(v):
    if v is None:
        return set()
    return set(v) if isinstance(v, list) else {v}


class Scene:
    """A rebuilt scene plus pixel positions in each saved image style (verified against the dataset image)."""

    def __init__(self, ds, scene_id):
        self.r = rebuild(ds, scene_id)
        self.cells = label_cells(self.r)
        self.ds, self.id = Path(ds), scene_id
        self._px = {}

    def px(self, style):
        if style not in self._px:
            if style == "map":
                s, p, nm, P, key = (self.r[k] for k in ("s", "p", "nm", "P", "key"))
                fig = render_map.render(s, p, nm, P, title=self._title(key) + " | topographic map")
                self._px[style] = fig.tm_px
                plt.close(fig)
            else:
                self._px[style] = lambda i: (_px(i)[0], _px(i)[1] + 30)
        return self._px[style]

    def _title(self, key):
        km = N * CELL_M / 1000
        terr = key.get("terrain", "synthetic")
        tag = (f"Region TM-{key['seed']:05d} | difficulty {key['level']}/5 | {km:.0f} km x {km:.0f} km"
               if terr == "synthetic" else
               f"{realterrain.LOCATIONS[terr][2]} | hypothetical facility | {km:.0f} km x {km:.0f} km")
        return tag + (" | counterfactual twin" if key.get("pair_of") else "")

    def water_cells(self, t):
        """The true water path behind a question, to draw as a line."""
        s, p = self.r["s"], self.r["p"]
        q = t["qid"]
        if q in ("Q1", "Q2", "Q3", "Q8", "Q10", "Q5"):
            pos = {c: k for k, c in enumerate(s["path"])}
            hits = [pos[v] for v in p["villages"] if v in pos] + [pos[c] for c in
                                                                    (p.get("plume") or {}).get("points", []) if c in pos]
            end = (max(hits) if hits else 40) + 10
            return [s["path"][: end]]
        if q == "Q7" and p.get("intake"):
            it = p["intake"]["intake"]
            out = []
            for v in p["villages"]:
                tr = trace(s["rec"], v)
                if it in tr:
                    out.append(tr[: tr.index(it) + 1])
            return out
        if q == "Q6" and p.get("siting"):
            return [trace(s["rec"], o)[:80] for o in p["siting"]["site_outfalls"]]
        return []


def draw_overlay(sc, t, pred, model, width=720):
    """The image the model saw, with the true path and the model's picks marked."""
    im = Image.open(sc.ds / t["image"]).convert("RGB")
    px = sc.px(t["style"])
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for cells in ([] if t["style"] == "thermal" else sc.water_cells(t)):     # thermal: the colours ARE the evidence
        pts = [px(c) for c in cells]
        if len(pts) > 1:
            d.line(pts, fill=PATH + (235,), width=5, joint="curve")
    truth, got = as_set(t["answer"]), as_set(pred)
    f = font(17)
    for lab in sorted(truth | got):
        cell = sc.cells.get(lab)
        if cell is None:
            continue
        x, y = px(cell)
        col, mark = (RIGHT, "✓") if lab in truth and lab in got else (WRONG, "✗") if lab in got else (MISSED, "?")
        r = 17
        d.ellipse((x - r, y - r, x + r, y + r), outline=col + (255,), width=5)
        d.ellipse((x - r - 3, y - r - 3, x + r + 3, y + r + 3), outline=(255, 255, 255, 200), width=2)
        d.text((x + r + 2, y - r - 6), mark, font=f, fill=col + (255,), stroke_width=3, stroke_fill=(255, 255, 255, 255))
    im = Image.alpha_composite(im.convert("RGBA"), over).convert("RGB")
    s = width / im.width
    im = im.resize((width, round(im.height * s)), Image.LANCZOS)
    band = Image.new("RGB", (width, 74), PAPER)
    d = ImageDraw.Draw(band)
    ok = score(t, json.dumps({"answer": pred}))["correct"]
    d.text((12, 8), f"{short(model)} answered {fmt(pred)}   ·   key {fmt(t['answer'])}   {'✓' if ok else '✗'}",
           font=font(17), fill=RIGHT if ok else WRONG)
    x = 12
    for col, txt in ((PATH, "true water path"), (RIGHT, "right pick"), (WRONG, "wrong pick"), (MISSED, "missed")):
        d.rectangle((x, 46, x + 22, 58), fill=col)
        d.text((x + 28, 42), txt, font=font(15, False), fill=INK)
        x += 28 + d.textlength(txt, font=font(15, False)) + 22
    out = Image.new("RGB", (width, im.height + 74), PAPER)
    out.paste(im, (0, 0))
    out.paste(band, (0, im.height))
    return out


def fmt(v):
    if isinstance(v, list):
        return ", ".join(map(str, v)) if v else "none"
    return "none" if v is None else str(v)


def story(sc, t, pred):
    """What a wrong answer would mean on the ground. Returns a list of plain sentences."""
    q, truth, got = t["qid"], as_set(t["answer"]), as_set(pred)
    traps = {lab: kind for kind, labs in (t.get("traps") or {}).items() for lab in labs}
    out = []
    if q == "Q1":
        for v in sorted(truth - got):
            out.append(f"{v} receives the warm wastewater but would not be warned.")
        for v in sorted(got - truth):
            why = {"near_but_other_stream": "it is close to the data centre, but its water comes from another stream",
                   "upstream_same_stream": "it is upstream of the outfall, and water does not flow uphill"}.get(
                traps.get(v), "the wastewater never reaches it")
            out.append(f"{v} would be alarmed for nothing: {why}.")
    elif q == "Q2" and got:
        out.append(f"The wastewater reaches {fmt(t['answer'])} first; warning {fmt(pred)} first leaves "
                   f"{fmt(t['answer'])} exposed{' (the model fell for a nearby village on another stream)' if traps.get(fmt(pred)) == 'near_but_other_stream' else ''}.")
    elif q == "Q3" and got:
        kind = traps.get(fmt(pred))
        out.append({"too_late_after_village": f"A wetland at {fmt(pred)} would clean the water only after it has "
                                              f"already reached a village; the working site is {fmt(t['answer'])}.",
                    "upstream_of_outfall": f"A wetland at {fmt(pred)} sits upstream of the outfall and would never "
                                           f"see the wastewater; the working site is {fmt(t['answer'])}."}.get(
            kind, f"A wetland at {fmt(pred)} would not clean all the wastewater; the working site is {fmt(t['answer'])}."))
    elif q == "Q6" and got:
        p, s = sc.r["p"], sc.r["s"]
        k = int(fmt(pred)[1:]) - 1 if fmt(pred)[1:].isdigit() else None
        if k is not None and p.get("siting") and k < len(p["siting"]["site_outfalls"]):
            hit = [sc.r["nm"]["village"][v] for v in p["villages"] if v in set(trace(s["rec"], p["siting"]["site_outfalls"][k]))]
            out.append(f"Site {fmt(pred)} would be approved as safe, but its wastewater reaches {', '.join(hit) or 'a village'}; "
                       f"the safe site is {fmt(t['answer'])}.")
    elif q == "Q7":
        for v in sorted(truth - got):
            out.append(f"{v} shares the intake's water source but would be left out of water-sharing plans.")
        for v in sorted(got - truth):
            out.append(f"{v} is downstream of the intake and does not share its source.")
    elif q == "Q8":
        for m in sorted(truth - got):
            out.append(f"The river at {m} is more than 3 °C warmer than normal, but no heat warning would be raised.")
        for m in sorted(got - truth):
            why = {"cooled_downstream": "the water has cooled below 3 °C by then",
                   "other_stream": "it is on another stream"}.get(traps.get(m), "it is not that warm")
            out.append(f"A heat warning at {m} would be a false alarm: {why}.")
    elif q == "Q4":
        for f_ in sorted(got - truth):
            out.append(f"Farm {f_} lies higher than pond P: treated water cannot reach it by gravity.")
        for f_ in sorted(truth - got):
            out.append(f"Farm {f_} could take treated water by gravity but would be left out.")
    elif q == "Q5" and pred:
        out.append(f"The stream flows {t['answer']}, not {fmt(pred)}: the plume would be looked for in the wrong place.")
    elif q == "Q9" and pred is not None:
        out.append(f"The water at the point is {t['answer']} °C warmer than normal, not {fmt(pred)} °C.")
    elif q == "Q10" and pred is not None:
        out.append(f"The wastewater travels about {t['answer']} m to the first village, not {fmt(pred)} m.")
    return out


def mechanism(scenes, rows):
    """Distance vs flow: wrong picks nearest the outfall? first village caught more than later ones?"""
    stats = defaultdict(lambda: dict(wrong=0, nearest=0, chance=0.0, first=[0, 0], later=[0, 0]))
    for model, t, pred in rows:
        if t["qid"] != "Q1" or pred is None:
            continue
        sc = scenes[t["scene_id"]]
        s, p, nm = sc.r["s"], sc.r["p"], sc.r["nm"]
        lab = {nm["village"][v]: v for v in p["villages"]}
        truth, got = as_set(t["answer"]), as_set(pred) & set(lab)
        others = [v for v in lab if v not in truth]
        if others:
            dO = {v: dist(p["village_pos"][lab[v]], s["O"]) for v in others}
            near = min(others, key=dO.get)
            for v in got - truth:
                st = stats[model]
                st["wrong"] += 1
                st["nearest"] += v == near
                st["chance"] += 1 / len(others)
        pos = {c: k for k, c in enumerate(s["path"])}
        order = sorted((v for v in truth if lab.get(v) in pos), key=lambda v: pos[lab[v]])
        for k, v in enumerate(order):
            key = "first" if k == 0 else "later"
            stats[model][key][0] += v in got
            stats[model][key][1] += 1
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--frontier", default="results/frontier")
    ap.add_argument("--main-run", default="results/models")
    ap.add_argument("--out", default="results/analysis")
    a = ap.parse_args()
    ds, out = Path(a.dataset), Path(a.out)
    (out / "overlays").mkdir(parents=True, exist_ok=True)
    (out / "pairs").mkdir(parents=True, exist_ok=True)
    from thirstmap import errata
    bad = errata.load(ds)
    tasks = {t["task_id"]: t for t in map(json.loads, open(ds / "tasks.jsonl")) if t["task_id"] not in bad}

    def load(run, protocol):
        latest = {}
        for line in open(Path(run) / "responses.jsonl"):
            r = json.loads(line)
            if r["mode"] == "image" and not r.get("error") and r["task_id"] in tasks:
                latest[(r["model"], r["task_id"])] = r
        return [(m, tasks[tid], score(tasks[tid], r["raw"])["parsed"], protocol) for (m, tid), r in latest.items()]

    front = load(a.frontier, "batched")
    main_rows = [x for x in load(a.main_run, "single") if x[1]["qid"] == "Q1"]
    need = {t["scene_id"] for _, t, _, _ in front + main_rows}
    scenes = {}
    for sid in sorted(need):
        try:
            scenes[sid] = Scene(ds, sid)
        except RuntimeError as e:                                  # never use a scene we cannot reproduce
            print("skip", sid, e)
    front = [x for x in front if x[1]["scene_id"] in scenes]
    main_rows = [x for x in main_rows if x[1]["scene_id"] in scenes]

    # accuracy per model on the frontier set, to pick the best API model for the per-task overlays
    acc = defaultdict(list)
    for m, t, pred, _ in front:
        acc[m].append(score(t, json.dumps({"answer": pred}))["correct"])
    api = [m for m in acc if not m.startswith("hf:")]
    best_api = max(api, key=lambda m: sum(acc[m]) / len(acc[m])) if api else None
    best_open = max((m for m in acc if m.startswith("hf:")), key=lambda m: sum(acc[m]) / len(acc[m]), default=None)

    index = defaultdict(dict)
    stories = []
    for m, t, pred, proto in front:
        ok = score(t, json.dumps({"answer": pred}))["correct"]
        if not ok:
            for line in story(scenes[t["scene_id"]], t, pred):
                stories.append(dict(model=m, task_id=t["task_id"], qid=t["qid"], protocol=proto, text=line))
        if m == best_api and t["qid"] in LABEL_Q:
            name = f"{t['task_id']}__{short(m)}.jpg"
            draw_overlay(scenes[t["scene_id"]], t, pred, m).save(out / "overlays" / name, quality=82)
            index[t["task_id"]][m] = f"overlays/{name}"

    # pair figures: original | twin, per model, for every pair answered in the frontier set
    by = {(m, t["task_id"]): (t, pred) for m, t, pred, _ in front}
    pairs = []
    for (m, tid), (t, pred) in by.items():
        if t.get("variant") != "base" or not t.get("pair_id") or m not in (best_api, best_open):
            continue
        cf = next((x for x in tasks.values() if x.get("pair_id") == t["pair_id"] and x.get("variant") == "counterfactual"), None)
        if not cf or (m, cf["task_id"]) not in by or t["qid"] not in LABEL_Q:
            continue
        cpred = by[(m, cf["task_id"])][1]
        a_img = draw_overlay(scenes[t["scene_id"]], t, pred, m, width=640)
        b_img = draw_overlay(scenes[cf["scene_id"]], cf, cpred, m, width=640)
        W2 = 640 * 2 + 24
        probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        words, lines, cur = f"{short(m)} · {t['question']}".split(), [], ""
        for w in words:                                            # wrap the question to the figure width
            nxt = (cur + " " + w).strip()
            if probe.textlength(nxt, font=font(19)) > W2 - 28 and cur:
                lines.append(cur); cur = w
            else:
                cur = nxt
        lines.append(cur)
        head = 20 + 28 * len(lines) + 34
        fig = Image.new("RGB", (W2, max(a_img.height, b_img.height) + head), PAPER)
        d = ImageDraw.Draw(fig)
        for k, ln in enumerate(lines):
            d.text((14, 10 + 28 * k), ln, font=font(19), fill=INK)
        d.text((14, 14 + 28 * len(lines)), f"Original (left) and twin (right): {cf.get('cf_change', 'one change')}.",
               font=font(16, False), fill=INK)
        fig.paste(a_img, (0, head))
        fig.paste(b_img, (640 + 24, head))
        name = f"{t['pair_id']}__{short(m)}.jpg"
        fig.save(out / "pairs" / name, quality=84)
        ok_a = score(t, json.dumps({"answer": pred}))["correct"]
        ok_b = score(cf, json.dumps({"answer": cpred}))["correct"]
        pairs.append(dict(model=m, pair_id=t["pair_id"], qid=t["qid"], file=f"pairs/{name}", original_right=ok_a,
                          twin_right=ok_b, same_answer=as_set(pred) == as_set(cpred), change=cf.get("cf_change"),
                          question=t["question"], original=dict(answer=t["answer"], model=pred),
                          twin=dict(answer=cf["answer"], model=cpred)))

    mech = mechanism(scenes, [(m, t, p) for m, t, p, _ in front] + [(m, t, p) for m, t, p, _ in main_rows])
    (out / "analysis.json").write_text(json.dumps(dict(
        best_api=best_api, best_open=best_open, overlays=index, pairs=sorted(pairs, key=lambda x: (x["model"], x["pair_id"])),
        stories=stories, mechanism={m: v for m, v in mech.items()}), indent=1, ensure_ascii=False, default=str))
    n_wrong = sum(v["wrong"] for v in mech.values())
    n_near = sum(v["nearest"] for v in mech.values())
    exp = sum(v["chance"] for v in mech.values())
    print(f"{len(scenes)} scenes rebuilt; {sum(len(v) for v in index.values())} overlays; {len(pairs)} pair figures; "
          f"{len(stories)} consequence lines")
    print(f"wrong Q1 villages that were the nearest non-receiving village: {n_near}/{n_wrong} (chance {exp:.1f})")
    for m, v in mech.items():
        f, l = v["first"], v["later"]
        print(f"  {short(m)}: first village caught {f[0]}/{f[1]}, later villages {l[0]}/{l[1]}; "
              f"nearest-village wrong picks {v['nearest']}/{v['wrong']}")


if __name__ == "__main__":
    main()
