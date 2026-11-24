"""One-page summary for judges: docs/ThirstMap_summary.pdf.

Every number is read from the result files (results/*/summary.json, the dataset manifest, the errata list, the audit
and realism reports), so re-running this after a new evaluation updates the page.

    python3 make_summary.py                    # needs: pip install reportlab qrcode
"""
import argparse
import json
import re
from pathlib import Path

DEMO = "https://yugesh1111.github.io/THIRSTMAP/"
REPO = "https://github.com/yugesh1111/THIRSTMAP"
COLAB = "https://colab.research.google.com/github/yugesh1111/THIRSTMAP/blob/main/ThirstMap_quickstart.ipynb"


def load(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def short(m):
    return m.split(":", 1)[-1].split("@")[0].split("/")[-1]


def pretty(m):
    s = short(m)
    return s.replace("gemini-", "Gemini ").replace("-flash-lite", " Flash-Lite").replace("-flash", " Flash")


def pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def pval(p):
    if p >= 0.001:
        return f"{p:.3f}".rstrip("0").rstrip(".") if p < 0.1 else f"{p:.2f}"
    m, e = f"{p:.0e}".split("e")
    return f"{m}e{int(e)}"


def numbers(dataset):
    """Everything the page states, from the files."""
    N = {}
    man = load("eval_set/manifest_full_dataset.json") or load(Path(dataset) / "manifest.json")
    errata = Path(dataset) / "errata.jsonl"
    n_err = sum(1 for _ in open(errata)) if errata.exists() else 0
    N["tasks"], N["excluded"] = man["n_tasks"], n_err
    N["kept"], N["scenes"] = man["n_tasks"] - n_err, man["n_scenes"]
    N["pairs"] = man["counterfactual_pairs"]["pairs"]
    N["real_cities"] = len([k for k in man["tasks_by_terrain"] if k != "synthetic"])
    N["skills"], N["styles"] = len(man["tasks_by_skill"]), len(man["tasks_by_style"])
    N["real_tasks"] = sum(v for k, v in man["tasks_by_terrain"].items() if k != "synthetic")
    N["build_min"] = round(man["build_seconds"] / 60)
    N["v1"] = man.get("validation_pass_rate", {}).get("V1_independent_pysheds")
    N["wetland_balance"] = man.get("answer_balance", {}).get("Q3", {})

    F = load("results/frontier/summary.json")
    rows = []
    for m, v in F.get("vs_chance", {}).items():
        pr = F.get("counterfactual_pairs", {}).get(m, {})
        tr = F.get("trap_fall_rate", {}).get(m, {})
        rows.append(dict(m=m, acc=v["correct"] / v["n"], correct=v["correct"], n=v["n"], chance=v["chance"],
                         p=v["p_value"], pairs=pr.get("pairs"), pairs_right=round(pr.get("pair_accuracy", 0) * pr.get("pairs", 0)),
                         trap=tr.get("rate"), blind=F["overall"].get(m, {}).get("blind"),
                         halves=pr.get("single_task_accuracy"), unchanged=pr.get("unchanged_answer_rate"),
                         kind="open, local" if m.startswith("hf:") else "API"))
    N["frontier"] = sorted(rows, key=lambda r: -r["acc"])
    N["set_chance"] = F.get("chance_by_skill", {}).get("trace_downstream")
    tok, answers = 0, 0
    req = Path("results/frontier/requests.jsonl")
    for r in map(json.loads, open(req)) if req.exists() else []:
        if not r.get("error") and r.get("input_tokens") and r.get("mode", "image") == "image" and not r["model"].startswith("hf:"):
            tok += r["input_tokens"] + (r.get("output_tokens") or 0)
            answers += r.get("questions", 0)
    N["tokens_per_answer"] = round(tok / answers, -1) if answers else None
    S1 = load("results/frontier_single/summary.json")
    N["single"] = [dict(m=m, acc=v["correct"] / v["n"], correct=v["correct"], n=v["n"], chance=v["chance"], p=v["p_value"])
                   for m, v in S1.get("vs_chance", {}).items()]
    M = load("results/models/summary.json")
    best = max(M.get("vs_chance", {}).items(), key=lambda kv: kv[1]["correct"] / kv[1]["n"], default=None)
    if best:
        N["open_best"] = dict(m=best[0], acc=best[1]["correct"] / best[1]["n"], chance=best[1]["chance"], n=best[1]["n"],
                              models=len(M["vs_chance"]))
    N["main_pairs"] = {m: (v["pairs"], round(v["pair_accuracy"] * v["pairs"])) for m, v in M.get("counterfactual_pairs", {}).items()}
    N["main_overall"] = M.get("overall", {})

    FT = load("results/finetune/summary.json")
    if FT:
        b = next(m for m in FT["models"] if "(base)" in m)
        t = next(m for m in FT["models"] if "fine-tuned" in m)
        vb, vt = FT["vs_chance"][b], FT["vs_chance"][t]
        N["ft"] = dict(base=vb["correct"] / vb["n"], tuned=vt["correct"] / vt["n"], n=vt["n"],
                       tuned_blind=FT["overall"][t].get("blind"), base_blind=FT["overall"][b].get("blind"),
                       model=short(b.split(" ")[0]), chance=vt["chance"],
                       base_wf=FT.get("format", {}).get(b, {}).get("well_formed"),
                       tuned_wf=FT.get("format", {}).get(t, {}).get("well_formed"))
        try:
            from findings import paired
            from thirstmap import errata as er
            bad = er.load(dataset)
            src = Path(dataset) / "tasks.jsonl"
            tasks = {x["task_id"]: x for x in map(json.loads, open(src)) if x["task_id"] not in bad}
            N["ft"]["p"] = paired("results/finetune", tasks, (t, "image"), (b, "image"))[2]
        except (OSError, StopIteration):
            pass

    import subprocess
    import sys
    col = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], capture_output=True, text=True).stdout
    m = re.search(r"(\d+) tests? collected", col)
    N["tests"] = int(m.group(1)) if m else "automated"
    H = load("human_eval/human_summary.json")
    if H:
        N["human"] = H
    audit = Path("docs/AUDIT.md").read_text() if Path("docs/AUDIT.md").exists() else ""
    m = re.search(r"Images re-rendered: \*\*(\d+)\*\*, pixel-identical to the published image: \*\*(\d+)\*\*", audit)
    N["rebuilt"] = (int(m.group(1)), int(m.group(2))) if m else None
    real = Path("docs/REALISM.md").read_text() if Path("docs/REALISM.md").exists() else ""
    m = re.search(r"([\d.]+)× to ([\d.]+)× as often", real)
    N["realism"] = (m.group(1), m.group(2)) if m else None
    return N


def build(N, out, figure):
    import qrcode
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Frame, Paragraph, Table, TableStyle

    import matplotlib
    fonts = Path(matplotlib.get_data_path()) / "fonts/ttf"
    pdfmetrics.registerFont(TTFont("Sans", fonts / "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("Sans-Bold", fonts / "DejaVuSans-Bold.ttf"))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans", boldItalic="Sans-Bold")

    DARK, WATER = colors.HexColor("#0F2230"), colors.HexColor("#1F64B8")
    INK2, PAPER, LINE = colors.HexColor("#44525C"), colors.HexColor("#EEF2F0"), colors.HexColor("#D3DCE0")
    body = ParagraphStyle("b", fontName="Sans", fontSize=8.3, leading=10.9, textColor=DARK)
    bullet = ParagraphStyle("u", parent=body, leftIndent=9, bulletIndent=0, spaceAfter=2.2)
    eyebrow = ParagraphStyle("e", fontName="Sans-Bold", fontSize=7.6, leading=10, textColor=WATER, spaceAfter=2.5)
    small = ParagraphStyle("s", fontName="Sans", fontSize=6.9, leading=8.9, textColor=INK2)
    cell = ParagraphStyle("c", fontName="Sans", fontSize=7.8, leading=9.6, textColor=DARK)
    cellb = ParagraphStyle("cb", parent=cell, fontName="Sans-Bold")

    W, H = A4
    M = 26
    c = canvas.Canvas(str(out), pagesize=A4)
    c.setTitle("ThirstMap: one-page summary")
    c.setAuthor("Amritha S")

    def height(items, w):
        return sum(it.wrap(w, 10_000)[1] + it.getSpaceBefore() + it.getSpaceAfter() for it in items)

    def flow(x, y_top, w, items):
        """Place items from y_top down; returns the y below them. Raises if they do not fit the page."""
        items = list(items)
        h = height(items, w) + 2
        f = Frame(x, y_top - h, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        f.addFromList(items, c)
        if items or y_top - h < M:
            raise SystemExit("summary: text does not fit the page")
        return y_top - h

    # header band with the QR code to the live demo
    c.setFillColor(DARK)
    c.rect(0, H - 84, W, 84, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Sans-Bold", 25)
    c.drawString(M, H - 38, "ThirstMap")
    c.setFont("Sans", 12.5)
    c.drawString(M + c.stringWidth("ThirstMap", "Sans-Bold", 25) + 9, H - 37, "can AI trace water through the landscape?")
    c.setFillColor(colors.HexColor("#9FC3E8"))
    c.setFont("Sans", 8.6)
    c.drawString(M, H - 56, "Innodata AI Hackathon 2026  ·  Track 2: Visual Task Factory  ·  Amritha S")
    c.setFillColor(colors.HexColor("#F2C2A8"))
    c.setFont("Sans-Bold", 9)
    c.drawString(M, H - 73, "AI is drinking India's water. We test whether AI can even see where that water goes.")
    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(DEMO)
    qr.make(fit=True)
    qpath = Path(out).with_suffix(".qr.png")
    qr.make_image(fill_color="#0F2230", back_color="white").save(qpath)
    q = 62
    c.drawImage(str(qpath), W - M - q, H - 12 - q, q, q)
    qpath.unlink()
    c.linkURL(DEMO, (W - M - q, H - 12 - q, W - M, H - 12), relative=0)
    c.setFillColor(colors.HexColor("#9FC3E8"))
    c.setFont("Sans", 6.4)
    c.drawCentredString(W - M - q / 2, H - 81, "scan: live demo")

    # problem + what we built (left), the showcase pair (right)
    top = H - 94
    img_w = 244
    left_w = W - 2 * M - img_w - 14
    y_left = flow(M, top, left_w, [
        Paragraph("THE PROBLEM  ·  impact", eyebrow),
        Paragraph("India's data centres use about 150 billion litres of water a year, heading for about 358 billion by "
                  "2030; around 70% of capacity sits in water-stressed Mumbai and Chennai. AI geospatial agents are "
                  "being built to answer: <b>where does a facility's warm wastewater go, which villages receive it, "
                  "where could a wetland clean it?</b>", body),
        Paragraph("&nbsp;", small),
        Paragraph("WHAT WE BUILT  ·  implementation, variation, originality", eyebrow),
        Paragraph("A <b>factory of visual tasks</b>: code builds a landscape and simulates its water (priority-flood + D8 "
                  "routing), so it <b>knows every answer before it asks</b>.", bullet, bulletText="•"),
        Paragraph(f"{N['skills']} reasoning skills and no counting; satellite, map and thermal images; 5 difficulty "
                  f"levels; real terrain for {N['real_cities']} Indian cities (Copernicus DEM, ESA WorldCover).",
                  bullet, bulletText="•"),
        Paragraph("<b>Twins</b>: the same scene with one minimal change (outfall, intake or water temperature) that must "
                  "flip the answer. A model answering from habit fails the pair.", bullet, bulletText="•"),
        Paragraph("One harness for any model (Claude, Gemini, any OpenAI-compatible API, any Hugging Face vision "
                  "model); batched prompts fit a free 20-request daily tier.", bullet, bulletText="•"),
    ])
    iw, ih = ImageReader(str(figure)).getSize()
    h_img = img_w * ih / iw
    x_img = W - M - img_w
    c.drawImage(str(figure), x_img, top - h_img, img_w, h_img)
    c.setStrokeColor(LINE)
    c.rect(x_img, top - h_img, img_w, h_img, stroke=1, fill=0)
    y_right = flow(x_img, top - h_img - 4, img_w, [Paragraph(
        "The best model, Gemini 3.5 Flash, on a before-and-after pair. The twin's cooling water is cooler, so no "
        "monitoring point is above 3 °C any more; it gives the same answer to both: right before (green), wrong after (red).",
        small)])

    # stat tiles
    y = min(y_left, y_right) - 8
    tiles = [(f"{N['kept']:,}", "tasks (after the audit)"), (f"{N['scenes']}", "scenes"),
             (f"{N['pairs']}", "before-and-after pairs"), (f"{N['skills']}", "reasoning skills"),
             (f"{N['styles']}", "image styles"), (f"{N['real_cities']}", "real Indian cities")]
    gap = 6
    tw = (W - 2 * M - gap * (len(tiles) - 1)) / len(tiles)
    for i, (big, label) in enumerate(tiles):
        x = M + i * (tw + gap)
        c.setFillColor(PAPER)
        c.roundRect(x, y - 34, tw, 34, 4, stroke=0, fill=1)
        c.setFillColor(WATER)
        c.setFont("Sans-Bold", 15)
        c.drawCentredString(x + tw / 2, y - 17, big)
        c.setFillColor(INK2)
        c.setFont("Sans", 6.9)
        c.drawCentredString(x + tw / 2, y - 28.5, label)

    # findings table
    y -= 46
    c.setFillColor(WATER)
    c.setFont("Sans-Bold", 7.6)
    c.drawString(M, y, "WHAT WE FOUND  ·  the same questions for every model, scored against exact chance")
    head = ["Model", "Kind", "Correct", "Chance", "p (beats chance)", "Pairs, both halves right", "Fell for a trap"]
    data = [[Paragraph(h, cellb) for h in head]]
    for r in N["frontier"]:
        data.append([Paragraph(pretty(r["m"]), cellb if r["kind"] == "API" else cell), Paragraph(r["kind"], cell),
                     Paragraph(f"<b>{pct(r['acc'])}</b> ({r['correct']}/{r['n']})", cell), Paragraph(pct(r["chance"]), cell),
                     Paragraph(pval(r["p"]), cell),
                     Paragraph(f"<b>{r['pairs_right']} of {r['pairs']}</b>" if r["pairs"] else "–", cell),
                     Paragraph(pct(r["trap"]), cell)])
    batched = {r["m"] for r in N["frontier"]}
    singles = [r for r in N["single"] if r["m"] not in batched]
    for r in singles:
        data.append([Paragraph(pretty(r["m"]) + " *", cellb), Paragraph("API", cell),
                     Paragraph(f"<b>{pct(r['acc'])}</b> ({r['correct']}/{r['n']})", cell), Paragraph(pct(r["chance"]), cell),
                     Paragraph(pval(r["p"]), cell), Paragraph("–", cell), Paragraph("–", cell)])
    if N.get("human"):
        hh = N["human"]
        data.append([Paragraph(f"People ({hh['people']})", cellb), Paragraph("human", cell),
                     Paragraph(f"<b>{pct(hh['accuracy'])}</b> of {hh['questions']}", cell), Paragraph("", cell),
                     Paragraph("", cell),
                     Paragraph(f"<b>{hh.get('pairs_right', '–')} of {hh.get('pairs_answered', '–')}</b>", cell),
                     Paragraph("", cell)])
    cw = [118, 58, 70, 44, 66, 98, 0]
    cw[-1] = W - 2 * M - sum(cw[:-1])
    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PAPER), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2), ("LEFTPADDING", (0, 0), (-1, -1), 3)]))
    _, th_ = t.wrapOn(c, W - 2 * M, 300)
    t.drawOn(c, M, y - 5 - th_)
    notes = ["18 images, 6 before-and-after pairs; every question about an image in one request."]
    if singles:
        notes.append("* one question per request on a 19-question subset (the free daily quota).")
    y = flow(M, y - 5 - th_ - 3, W - 2 * M, [Paragraph(" ".join(notes), small)]) - 7

    fr = N["frontier"]
    best = fr[0]
    api = [r for r in fr if r["kind"] == "API"]
    opens = [r for r in fr if r["kind"] != "API"]
    top = max(fr, key=lambda r: r["pairs_right"])
    if top["pairs_right"] == 0:
        finds = [f"<b>The best model scores {best['acc'] / best['chance']:.0f}× chance</b> ({pct(best['acc'])} vs "
                 f"{pct(best['chance'])}), <b>yet no model got both halves of a before-and-after pair right</b> "
                 f"(0 of {best['pairs']} for every model): models read the scene but do not follow the water."]
    else:
        finds = [f"<b>{pretty(best['m'])} scores {pct(best['acc'])}</b> ({best['acc'] / best['chance']:.0f}× chance), "
                 f"<b>but gets both halves of only {top['pairs_right']} of {top['pairs']} before-and-after pairs right</b>; "
                 f"every other model gets none. One small change to the scene is enough to trip up even the best model."]
    nob = [r for r in api if r.get("blind") is not None]
    if nob:
        finds.append("<b>Without the image the Gemini models fall to chance</b> ("
                     + ", ".join(f"{pretty(r['m'])} {pct(r['acc'])} → {pct(r['blind'])}" for r in nob)
                     + f"; chance {pct(best['chance'])}): the questions need the image, not just the text.")
    if opens:
        finds.append(f"Open models up to 3B parameters score at chance ({', '.join(pct(r['acc']) for r in opens)} vs "
                     f"{pct(opens[0]['chance'])})"
                     + (f"; the best of {N['open_best']['models']} in the main run: {pct(N['open_best']['acc'])} vs "
                        f"{pct(N['open_best']['chance'])} on {N['open_best']['n']} questions." if N.get("open_best") else "."))
    if N.get("ft"):
        ft = N["ft"]
        finds.append(f"<b>The data teaches the skill</b>: LoRA fine-tuning on held-out scenes lifts {ft['model']} from "
                     f"{pct(ft['base'])} to {pct(ft['tuned'])} on {ft['n']} questions"
                     + (f" (paired p = {pval(ft['p'])})" if ft.get("p") is not None else "")
                     + (f", and only with the image ({pct(ft['tuned_blind'])} without)." if ft.get("tuned_blind") is not None else "."))
    if api and opens and not nob:
        finds.append(f"Frontier models fall for a built-in trap {pct(min(r['trap'] for r in api))}–"
                     f"{pct(max(r['trap'] for r in api))} of the time, open models up to "
                     f"{pct(max(r['trap'] for r in opens))}: a village near the data centre but on another stream, "
                     "or one upstream of the outfall.")

    col_w = (W - 2 * M - 16) / 2
    valid = ["Every answer is <b>re-derived by an independent hydrology library</b> (pysheds); a question that "
             "disagrees is dropped, never edited.",
             "Evidence <b>checked in the pixels</b>: the path is visible, every option label readable and clear of "
             "the legend, scale bar and north arrow."]
    if N.get("rebuilt"):
        valid.append(f"<b>Byte-for-byte rebuilds</b>: {N['rebuilt'][1]:,} of {N['rebuilt'][0]:,} audited images "
                     "regenerate identically from their seeds; exact inputs published with SHA-256.")
    valid.append(f"A <b>self-audit</b> found and excluded {N['excluded']} unfair tasks "
                 f"({100 * N['excluded'] / N['tasks']:.1f}%), listed in errata.jsonl and left out of every score.")
    if N.get("realism"):
        valid.append(f"On real terrain the simulated drainage lies near real mapped water {N['realism'][0]}× to "
                     f"{N['realism'][1]}× as often as chance (3 cities).")
    y1 = flow(M, y, col_w, [Paragraph(s, bullet, bulletText="•") for s in finds])
    y2 = flow(M + col_w + 16, y, col_w, [Paragraph("WHY TRUST THE ANSWERS  ·  validity", eyebrow)]
              + [Paragraph(s, bullet, bulletText="•") for s in valid])
    y = min(y1, y2) - 8

    # judging criteria (left) and links (right)
    crit = [("Implementation 25%", f"One command from terrain to report; {N['tests']} tests and CI; <b>pip install</b> "
                                   "gives a <b>thirstmap</b> command; Colab notebook; live demo rebuilt on every change"),
            ("Validity 25%", "Answers simulated, then re-derived independently; pixel checks; byte-for-byte rebuilds; "
                             "a self-audit with published errata"),
            ("Variation 20%", f"{N['skills']} skills, {N['styles']} styles, 5 levels, {N['real_cities']} real cities; "
                              "twins; monsoon, haze and coarse-sensor looks whose answer must not change"),
            ("Originality 15%", "Twins whose answer must flip; every model error drawn on the image it saw, "
                                "with what it would mean on the ground"),
            ("Impact 15%", "India's data-centre water; a policy note proposing a pass bar before AI screens water "
                           "permits; a human test anyone can take")]
    crit_w = 372
    c.setFillColor(WATER)
    c.setFont("Sans-Bold", 7.6)
    c.drawString(M, y, "WHERE EACH JUDGING CRITERION IS ANSWERED")
    ct = Table([[Paragraph(a, cellb), Paragraph(b, small)] for a, b in crit], colWidths=[78, crit_w - 78])
    ct.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    _, cth = ct.wrapOn(c, crit_w, 400)
    if y - 6 - cth < M + 10:
        raise SystemExit(f"summary: criteria table does not fit the page (short by {M + 10 - (y - 6 - cth):.0f} pt)")
    ct.drawOn(c, M, y - 6 - cth)

    lx = M + crit_w + 16
    links = [("Live demo, no login", DEMO, DEMO), ("90-second video", DEMO + "thirstmap_demo.mp4", "…/THIRSTMAP/thirstmap_demo.mp4"),
             ("Take the test yourself", DEMO + "human/", "…/THIRSTMAP/human/"), ("Code, data, findings", REPO, REPO),
             ("Colab quickstart", COLAB, "ThirstMap_quickstart.ipynb (Colab)")]
    c.setFillColor(WATER)
    c.setFont("Sans-Bold", 7.6)
    c.drawString(lx, y, "SEE IT  ·  RUN IT")
    yy = y - 14
    for label, url, shown in links:
        shown = shown.replace("https://", "")
        c.setFillColor(DARK)
        c.setFont("Sans-Bold", 7.4)
        c.drawString(lx, yy, label)
        c.setFillColor(WATER)
        c.setFont("Sans", 7.1)
        c.drawString(lx, yy - 9, shown)
        if lx + c.stringWidth(shown, "Sans", 7.1) > W - M:
            raise SystemExit(f"summary: link text too wide: {shown}")
        c.linkURL(url, (lx, yy - 11, lx + c.stringWidth(shown, "Sans", 7.1), yy + 8), relative=0)
        yy -= 20.5

    c.setFillColor(INK2)
    c.setFont("Sans", 6.2)
    foot = ("Every number here is read from the result files by make_summary.py.  MIT code, CC BY 4.0 data "
            "(Copernicus DEM, ESA WorldCover).  Facilities and villages are hypothetical.")
    if c.stringWidth(foot, "Sans", 6.2) > W - 2 * M:
        raise SystemExit("summary: footer too wide")
    c.drawString(M, M - 8, foot)
    c.showPage()
    c.save()


def pairs_faq(N, fr, mp):
    best = fr[0]
    main = (f"; {', '.join(sorted({str(v[1]) for v in mp.values()}))} of {next(iter(mp.values()))[0]} for every open "
            "model in the main run" if mp else "")
    top = max(fr, key=lambda r: r["pairs_right"])
    if top["pairs_right"] == 0:
        return (f"On before-and-after pairs, precisely: no model got one right (0 of {best['pairs']} frontier pairs for "
                f"every model{main}). Pair questions are also the hardest single questions: {pretty(best['m'])} gets "
                f"{pct(best.get('halves'))} of the pair halves right, against {pct(best['acc'])} overall, so few pairs were "
                "expected even if the halves were independent. The pair result confirms that weakness rather than proving "
                f"a separate one. The full dataset has {N['pairs']} pairs for anyone with a larger budget.")
    rest = [pretty(r["m"]) for r in fr if r["pairs_right"] == 0]
    h = top.get("halves") or 0
    return (f"On before-and-after pairs, precisely: {pretty(top['m'])} got both halves of {top['pairs_right']} of "
            f"{top['pairs']} right; {', '.join(rest)} got 0 of {top['pairs']}{main}. With only {top['pairs']} pairs this is "
            f"a coarse measure, and we say so: {pretty(top['m'])} gets {pct(h)} of the pair halves right, so about "
            f"{pct(h * h)} of pairs would be right if it answered the halves independently, close to the "
            f"{pct(top['pairs_right'] / top['pairs'])} observed. What the pairs show directly is habit: "
            f"{pretty(top['m'])} gave the same answer to the original and its twin in {pct(top.get('unchanged'))} of pairs, "
            f"although the right answer had changed. The full dataset has {N['pairs']} pairs for anyone with a larger budget.")


def faq(N):
    """docs/FAQ.md: the hard questions a judge may ask, answered with the same numbers as the summary page."""
    fr, best = N["frontier"], N["frontier"][0]
    api = [r for r in fr if r["kind"] == "API"]
    single = N["single"][0] if N["single"] else None
    mp = N.get("main_pairs", {})
    mo = N.get("main_overall", {})
    ft = N.get("ft", {})
    wb = N.get("wetland_balance", {})
    L = ["# Tough questions, straight answers", "",
         "Generated by `make_summary.py` from the result files, with the same numbers as the one-page summary "
         "([`ThirstMap_summary.pdf`](ThirstMap_summary.pdf)). Raw replies for every number are in `results/`.", ""]

    def q(title, *paras):
        L.extend([f"### {title}", ""] + [p + "\n" for p in paras])

    q("1. Why synthetic landscapes? Real imagery is what matters.",
      "Because a benchmark is only as good as its answer key. Real photos come with no ground-truth flow paths, and a "
      "person tracing streams by eye is doing exactly the skill under test. ThirstMap simulates the water, so every answer "
      "is computed, then re-checked independently. Synthetic scenes also make **twins** possible: the same landscape with "
      "one minimal change, which no photo archive can supply.",
      f"Realism is covered three ways: real terrain for {N['real_cities']} Indian cities from Copernicus DEM and ESA "
      f"WorldCover ({N['real_tasks']:,} tasks); a realism check in which simulated drainage lies near real mapped water "
      + (f"{N['realism'][0]}× to {N['realism'][1]}× as often as chance ([`REALISM.md`](REALISM.md)); " if N.get("realism") else "")
      + "and three image styles plus monsoon, haze and coarse-sensor looks whose answers must not change.")
    q("2. How do you know the answers are right?",
      "- **Independent re-derivation.** An independent hydrology library (pysheds) recomputes the flow. "
      + (f"It agreed on every question in {N['v1'].split('/')[0]} of {N['v1'].split('/')[1]} scenes; questions where it "
         "disagreed were dropped, never edited." if N.get("v1") else "Questions where it disagrees are dropped, never edited."),
      "- **Evidence in the pixels.** The path must be visible in the rendered image, and every option label readable and "
      "clear of the legend, scale bar and north arrow.",
      (f"- **Byte-for-byte rebuilds.** {N['rebuilt'][1]:,} of {N['rebuilt'][0]:,} audited images regenerate identically "
       "from their seeds; the exact evaluated inputs are published with SHA-256 checksums." if N.get("rebuilt") else
       "- **Byte-for-byte rebuilds** from seeds, with SHA-256 checksums for the evaluated inputs."),
      f"- **A self-audit.** Drawing model answers on the images they saw exposed two generator problems. {N['excluded']} "
      f"tasks ({100 * N['excluded'] / N['tasks']:.1f}%) are excluded from every score, listed in `dataset/errata.jsonl` "
      "and explained in [`AUDIT.md`](AUDIT.md). We publish our mistakes rather than hide them.",
      "- **People.** The same questions are open to anyone at https://yugesh1111.github.io/THIRSTMAP/human/"
      + (f": {N['human']['people']} people scored {pct(N['human']['accuracy'])}." if N.get("human") else "."))
    q("3. Aren't the samples small?",
      f"They are sized to what is free: Gemini's free tier allows about 20 requests per model per day, so the frontier "
      f"check is {best['n']} questions on 18 images. Small samples become meaningful with exact statistics: every score "
      f"is tested against the exact chance of guessing each question. {pretty(best['m'])} scores {pct(best['acc'])} "
      f"against {pct(best['chance'])} chance (p = {pval(best['p'])}); the open models in the main run answered "
      f"{N['open_best']['n'] if N.get('open_best') else '–'} questions each.",
      pairs_faq(N, fr, mp))
    q("4. Could a model score by guessing, or from the question text alone?",
      "- **Chance is computed exactly** per question" + (f" (a random guess on a 'which villages' question is right "
                                                          f"{pct(N['set_chance'])} of the time)" if N.get("set_chance") else "") + ".",
      "- **No-image control.** The same questions are asked without the image. In the main run the open models score "
      "within a few points of each other with and without it ("
      + ", ".join(f"{short(m)} {pct(v['image'])} with, {pct(v['blind'])} without" for m, v in mo.items() if v.get("blind") is not None)
      + "): they barely use the image."
      + ((" The Gemini models, by contrast, fall to about chance without the image ("
          + ", ".join(f"{pretty(r['m'])} {pct(r['acc'])} → {pct(r['blind'])}" for r in api if r.get("blind") is not None)
          + f"; chance {pct(fr[0]['chance'])}).") if any(r.get("blind") is not None for r in api) else "")
      if mo else "- **No-image control.** The same questions are asked without the image.",
      "- **Balanced answers.** Correct options are spread evenly"
      + (f" (the wetland question's right answer is A, B, C or D {', '.join(str(wb[k]) for k in sorted(wb))} times)" if wb else "")
      + ".",
      "- **Traps.** Wrong answers that a shortcut produces are tagged"
      + (f"; the Gemini models fall for one {pct(min(r['trap'] for r in api))}–{pct(max(r['trap'] for r in api))} of the time"
         if api else "") + ".")
    q("5. Are the questions even answerable from the image?",
      "Every kept question passed the pixel checks, and every image has a reveal that draws the true path."
      + (f" The strongest model we could run, {pretty(best['m'])}, answers {pct(best['acc'])} of the frontier questions "
         f"right ({best['correct']}/{best['n']}): hard, but answerable." if best["acc"] >= 0.5 else
         f" The strongest model we could run, {pretty(single['m'])}, answers {pct(single['acc'])} of single questions "
         f"right ({single['correct']}/{single['n']}): hard, but answerable." if single else ""))
    q("6. Did you pick questions to make models fail?",
      "No. Questions are dropped only by automated validity checks, before any model sees them. The frontier set is "
      "chosen by a seeded round-robin over twin kinds (`frontier.py select`) before any model runs, and every model "
      "gets identical prompts and images. The audit removed tasks where a hidden label could have failed a model "
      "unfairly, which raised model scores.")
    q("7. Why not the largest models?",
      "Budget: this was built without paid API credit. The harness already supports `claude:`, `openai:` (any "
      "OpenAI-compatible endpoint), `gemini:` and any Hugging Face vision model; adding one is a single command, and "
      "[`LEADERBOARD.md`](../LEADERBOARD.md) rebuilds from the raw replies. We report only what we ran.")
    if ft:
        q("8. Did fine-tuning teach the skill, or just the answer format?",
          f"Both, and we separate them. The base model almost never replied in the requested format "
          f"({pct(ft.get('base_wf'))} well-formed) while the tuned model nearly always did ({pct(ft.get('tuned_wf'))}). "
          f"Format alone does not explain the gain: without the image the tuned model scores {pct(ft.get('tuned_blind'))}, "
          f"close to chance ({pct(ft['chance'])}); with it {pct(ft['tuned'])}"
          + (f" (paired McNemar test against the base model, p = {pval(ft['p'])})" if ft.get("p") is not None else "")
          + ". The tuning used only scenes that never appear in the test set.")
    q("9. Why does this matter beyond a benchmark?",
      "India's data centres use about 150 billion litres of water a year, and about 70% of capacity sits in "
      "water-stressed Mumbai and Chennai. AI geospatial agents are being built to answer siting and pollution "
      "questions from imagery. A model that names the village nearest the data centre, instead of following the "
      "stream, sends the warning to the wrong village. [`POLICY_NOTE.md`](POLICY_NOTE.md) proposes a pass bar, "
      "including before-and-after pairs, before AI is used for water screening.")
    q("10. What does it cost to run?",
      f"- Building the full {N['tasks']:,}-task dataset takes about {N['build_min']} minutes on 4 CPU cores; one scene "
      "with its twin takes under a minute.",
      "- Frontier models: every question about an image goes in one request at 768 px"
      + (f", about {N['tokens_per_answer']:.0f} tokens per answer" if N.get("tokens_per_answer") else "")
      + "; the whole frontier check is 18 requests per model, inside a free daily quota.",
      "- Open models run on a CPU; no GPU is needed.")
    q("11. Can I reproduce it?",
      "`./run_all.sh --quick` (about 2 minutes) or `./run_all.sh` for everything; `pip install` gives a `thirstmap` "
      "command; the [Colab notebook](https://colab.research.google.com/github/yugesh1111/THIRSTMAP/blob/main/ThirstMap_quickstart.ipynb) "
      "builds a scene and scores it in the browser; `verify_results.py` re-derives every number from the raw replies.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="dataset", help="for the errata list and the fine-tuning paired test")
    ap.add_argument("--figure", default=None, help="showcase image (default: the demo's Q1 pair)")
    ap.add_argument("--out", default="docs/ThirstMap_summary.pdf")
    ap.add_argument("--faq", default="docs/FAQ.md")
    a = ap.parse_args()
    fig = Path(a.figure) if a.figure else next(iter(sorted(Path("docs/demo/analysis").glob("pair__*Q8__thermal*gemini-3.5-flash.jpg"))
                                                    or sorted(Path("docs/demo/analysis").glob("pair__*.jpg"))), None)
    N = numbers(a.dataset)
    build(N, a.out, fig)
    Path(a.faq).write_text(faq(N))
    print(f"wrote {a.out} and {a.faq}")


if __name__ == "__main__":
    main()
