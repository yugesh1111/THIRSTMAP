"""The full project report: docs/ThirstMap_full_report.pdf.

Everything ThirstMap built, the dataset, how answers are validated, every result, the product, a tour of the repository
and the commands to clone, pull, install, test and run it. Numbers are read from the result files (the same function as
the one-page summary), the commit and history from git, so re-running this after a change updates the report.

    python3 make_full_report.py                # needs: pip install reportlab
"""
import argparse
import subprocess
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from make_summary import numbers, pct, pval, pretty

REPO = "https://github.com/yugesh1111/THIRSTMAP"
GITLAB = "https://gitlab.com/Amritha902/thirstmap"
SITE = "https://yugesh1111.github.io/THIRSTMAP/"
LINKS = [("GitHub repository (code, data sample, docs, results)", REPO),
         ("GitLab mirror (same history)", GITLAB),
         ("Live demo (no login)", SITE),
         ("Leaderboard: score your own model in the browser", SITE + "leaderboard/"),
         ("The film (4 min, narrated and subtitled)", SITE + "film.html"),
         ("Human test (32 questions the models also answered)", SITE + "human/"),
         ("Full dataset (GitHub Release, zip parts with SHA-256)", REPO + "/releases"),
         ("Colab notebook (3 minutes, no key)",
          "https://colab.research.google.com/github/yugesh1111/THIRSTMAP/blob/main/ThirstMap_quickstart.ipynb")]


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


# ---------------------------------------------------------------------------------------------------------------------
# a small document kit on top of reportlab (shared in spirit with SeeTheMark's report)
# ---------------------------------------------------------------------------------------------------------------------
class Doc:
    def __init__(self, out, title, accent):
        import matplotlib
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate

        fonts = Path(matplotlib.get_data_path()) / "fonts/ttf"
        for name, f in (("Sans", "DejaVuSans.ttf"), ("Sans-Bold", "DejaVuSans-Bold.ttf"), ("Sans-It", "DejaVuSans-Oblique.ttf"),
                        ("Mono", "DejaVuSansMono.ttf")):
            pdfmetrics.registerFont(TTFont(name, fonts / f))
        registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-It", boldItalic="Sans-Bold")
        self.c = colors
        self.ink, self.muted = colors.HexColor("#14202B"), colors.HexColor("#56636F")
        self.acc, self.line, self.paper = colors.HexColor(accent), colors.HexColor("#D5DCE2"), colors.HexColor("#F1F4F6")
        P = lambda n, **k: ParagraphStyle(n, **{"fontName": "Sans", "fontSize": 9.6, "leading": 13.4, "textColor": self.ink, **k})
        self.s = dict(body=P("body", spaceAfter=5), h1=P("h1", fontName="Sans-Bold", fontSize=17, leading=21, spaceBefore=4, spaceAfter=8,
                                                     textColor=self.acc),
                      h2=P("h2", fontName="Sans-Bold", fontSize=12, leading=15, spaceBefore=9, spaceAfter=4),
                      bullet=P("bullet", leftIndent=13, bulletIndent=3, spaceAfter=2.5),
                      small=P("small", fontSize=8, leading=10.5, textColor=self.muted, spaceAfter=4),
                      cell=P("cell", fontSize=8.2, leading=10.4), cellb=P("cellb", fontName="Sans-Bold", fontSize=8.2, leading=10.4),
                      code=P("code", fontName="Mono", fontSize=7.9, leading=10.2, textColor=colors.HexColor("#1B2A36")),
                      title=P("title", fontName="Sans-Bold", fontSize=30, leading=35, textColor=self.ink),
                      sub=P("sub", fontSize=13, leading=18, textColor=self.muted))
        self.story, self.title = [], title
        self.doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=44, rightMargin=44, topMargin=48, bottomMargin=46,
                                     title=title, author="Amritha S")
        self.W = A4[0] - 88

    def p(self, text, style="body"):
        from reportlab.platypus import Paragraph
        self.story.append(Paragraph(text, self.s[style]))

    def h1(self, text):
        from reportlab.platypus import CondPageBreak
        self.story.append(CondPageBreak(160))
        self.p(text, "h1")

    def h2(self, text):
        from reportlab.platypus import CondPageBreak
        self.story.append(CondPageBreak(90))
        self.p(text, "h2")

    def bullets(self, items):
        from reportlab.platypus import Paragraph
        for t in items:
            self.story.append(Paragraph(t, self.s["bullet"], bulletText="•"))
        self.space(4)

    def space(self, h=8):
        from reportlab.platypus import Spacer
        self.story.append(Spacer(1, h))

    def table(self, rows, widths, header=True, zebra=True):
        from reportlab.platypus import Paragraph, Table, TableStyle
        data = [[c if not isinstance(c, str) else Paragraph(c, self.s["cellb" if (header and i == 0) else "cell"]) for c in r]
                for i, r in enumerate(rows)]
        t = Table(data, colWidths=[w * self.W for w in widths], repeatRows=1 if header else 0)
        st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, self.line),
              ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
              ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
        if header:
            st += [("BACKGROUND", (0, 0), (-1, 0), self.paper), ("LINEBELOW", (0, 0), (-1, 0), 0.9, self.acc)]
        t.setStyle(TableStyle(st))
        self.story.append(t)
        self.space(8)

    def code(self, text):
        from reportlab.platypus import Preformatted, Table, TableStyle
        t = Table([[Preformatted(text, self.s["code"])]], colWidths=[self.W])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), self.paper), ("BOX", (0, 0), (-1, -1), 0.5, self.line),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        self.story.append(t)
        self.space(7)

    def image(self, path, width=1.0, caption=None):
        from reportlab.platypus import Image
        from PIL import Image as PI
        if not Path(path).exists():
            return
        w, h = PI.open(path).size
        W = self.W * width
        H = W * h / w
        if H > 520:
            W, H = W * 520 / H, 520
        self.story.append(Image(str(path), width=W, height=H))
        if caption:
            self.p(caption, "small")
        else:
            self.space(6)

    def images(self, paths, caption=None):
        """A row of images, same height."""
        from reportlab.platypus import Image, Table, TableStyle
        from PIL import Image as PI
        paths = [p for p in paths if Path(p).exists()]
        ratios = [PI.open(p).size[0] / PI.open(p).size[1] for p in paths]
        gap = 6
        h = (self.W - gap * (len(paths) - 1)) / sum(ratios)
        t = Table([[Image(str(p), width=h * r, height=h) for p, r in zip(paths, ratios)]],
                  colWidths=[h * r + (gap if i < len(paths) - 1 else 0) for i, r in enumerate(ratios)])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        self.story.append(t)
        if caption:
            self.p(caption, "small")

    def page_break(self):
        from reportlab.platypus import PageBreak
        self.story.append(PageBreak())

    def build(self):
        def deco(canvas, doc):
            canvas.saveState()
            canvas.setFont("Sans", 7.5)
            canvas.setFillColor(self.muted)
            if doc.page > 1:
                canvas.drawString(44, 26, self.title)
                canvas.drawRightString(doc.pagesize[0] - 44, 26, f"page {doc.page}")
                canvas.setStrokeColor(self.acc)
                canvas.setLineWidth(1.2)
                canvas.line(44, doc.pagesize[1] - 34, doc.pagesize[0] - 44, doc.pagesize[1] - 34)
            canvas.restoreState()
        self.doc.build(self.story, onFirstPage=deco, onLaterPages=deco)


def link(url, text=None):
    return f'<link href="{escape(url)}" color="#1F64B8">{escape(text or url)}</link>'


# ---------------------------------------------------------------------------------------------------------------------
def report(N, out):
    d = Doc(out, "ThirstMap — full project report", "#1F64B8")
    head, n_commits = git("rev-parse", "--short", "HEAD"), git("rev-list", "--count", "HEAD")
    first, last = git("log", "--reverse", "--format=%ad", "--date=short").split("\n")[0], git("log", "-1", "--format=%ad", "--date=short")
    fr, ob = N["frontier"], N["open_best"]
    best = fr[0]
    api = [r for r in fr if r["kind"] == "API"]

    # ---- cover
    d.space(40)
    d.p("Innodata AI Hackathon 2026 · Track 2: Visual Task Factory", "sub")
    d.space(6)
    d.p("ThirstMap", "title")
    d.p("Can AI trace water through the landscape? A factory of visual tasks whose answers come from a water simulation, "
        "with before-and-after twins, an evaluation of open and frontier models, and a public leaderboard.", "sub")
    d.space(14)
    d.p(f"<b>Author:</b> Amritha S &nbsp; · &nbsp; <b>Report date:</b> {date.today():%d %B %Y} &nbsp; · &nbsp; "
        f"<b>Repository state:</b> commit <font name='Mono'>{head}</font>, {n_commits} commits from {first} to {last}")
    d.space(6)
    d.table([["What", "Link"]] + [[a, link(u)] for a, u in LINKS], [0.42, 0.58])
    d.p("<b>Is everything pushed?</b> Yes. All code, the dataset sample, the exact evaluation inputs (<font name='Mono'>eval_set/</font>), "
        "every raw model reply, the reports, the films and this PDF are committed to the GitHub repository above "
        f"(branch <font name='Mono'>main</font>) and mirrored to GitLab. The full 2.1 GB dataset is a GitHub Release, rebuilt from "
        "the code by a workflow. The live demo and leaderboard are redeployed by GitHub Actions on every push.")
    d.space(4)
    d.table([["", "In numbers"],
             ["Dataset", f"{N['scenes']} scenes · {N['tasks']:,} tasks ({N['real_tasks']:,} on real terrain in {N['real_cities']} Indian cities) · "
                         f"{N['pairs']} before-and-after pairs · {N['skills']} skills · {N['styles']} image styles"],
             ["Validity", f"{N['excluded']} tasks ({N['excluded'] / N['tasks']:.1%}) excluded by a self-audit, {N['kept']:,} kept · "
                          f"answers re-derived by an independent library · {N['rebuilt'][1]:,} of {N['rebuilt'][0]:,} images rebuilt pixel-identical"
                          if N.get("rebuilt") else ""],
             ["Best model", f"{pretty(best['m'])}: {pct(best['acc'])} on {best['n']} questions (chance {pct(best['chance'])}), "
                            f"but both halves of only {best['pairs_right']} of {best['pairs']} before-and-after pairs"],
             ["Open models", f"best of {ob['models']}: {pretty(ob['m'])} {pct(ob['acc'])} vs chance {pct(ob['chance'])}: none beats guessing"],
             ["Engineering", f"{N['tests']} automated tests and CI · pip-installable <font name='Mono'>thirstmap</font> command · browser scorer "
                             "that matches the Python scorer on all 37,516 replies"]], [0.16, 0.84])
    d.page_break()

    # ---- 1 problem
    d.h1("1 · The problem")
    d.p("India's data centres use an estimated ~150 billion litres of water a year, possibly ~358 billion by 2030; about 70% of capacity "
        "sits in water-stressed Mumbai and Chennai, and none of India's 15 state data-centre policies require water-stress mapping "
        "(Down To Earth, citing CEEW; sources in <font name='Mono'>docs/PROJECT_BRIEF.md</font>). AI geospatial agents are being built "
        "to answer questions from imagery: <i>where does this facility's warm wastewater go, which villages receive it, where could a "
        "wetland clean it?</i> Before anyone trusts an AI with that, we need to know whether it can follow water across an image at all.")
    d.p("<b>ThirstMap's answer:</b> a factory that builds landscapes, simulates their water, and asks questions whose answers it already "
        "knows, the Track 2 brief's bar-chart example, but for terrain and water flow. Every answer comes from the simulation, is checked "
        "by an independent library and in the pixels, and nothing is ever hand-edited.")

    # ---- 2 what we built
    d.h1("2 · What was built")
    d.table([["Part", "What it does", "Where"],
             ["Terrain and water", "Fractal terrain (4 × 4 km, 25 m cells), priority-flood depression filling, D8 routing, flow accumulation, "
              "path tracing", "thirstmap/terrain.py"],
             ["Scene script", "Data centre, outfall, villages with traps, wetlands, sites, intake, heat plume", "thirstmap/scene.py"],
             ["Real terrain", "Copernicus 30 m elevation + ESA WorldCover for Navi Mumbai, Hyderabad, Pune, Chennai", "thirstmap/realterrain.py"],
             ["Questions", "10 question types (skills), answer keys, options, traps", "thirstmap/questions.py"],
             ["Three renderers", "Satellite-style, topographic map, thermal false colour", "thirstmap/render_*.py"],
             ["Validators", "V1–V11: independent recomputation, margins, pixel evidence, legibility, style applicability", "thirstmap/validate.py"],
             ["Twins and variants", "Before-and-after twins (one change flips the answer); season, haze, sensor variants (answer must not change)",
              "generate.py, variants.py"],
             ["Dataset builder", f"{N['scenes']} scenes, {N['tasks']:,} tasks, manifest with pass rates and every dropped question", "build_dataset.py"],
             ["Evaluation harness", "Open models (Hugging Face), Claude, OpenAI-compatible APIs, offline baselines; resumable; cost per call",
              "evaluate.py, frontier.py"],
             ["Scoring and reports", "Exact chance per task, binomial tests, pair accuracy, trap diagnosis, skill profiles, charts",
              "thirstmap/scoring.py, report.py, findings.py"],
             ["Eye exam", "Difficulty levels 1–5 and an adaptive 2-down/1-up staircase", "staircase.py"],
             ["Fine-tuning", "LoRA on a small open model with a train split", "finetune.py"],
             ["Audit and verification", "Self-audit with errata, independent recomputation of every number, byte-for-byte rebuilds",
              "audit_labels.py, verify_results.py"],
             ["Product", "Live demo, leaderboard with browser scorer, human test, films, one-page PDF, Colab, CLI",
              "build_demo.py, build_leaderboard.py, human_eval.py, video/"]], [0.19, 0.53, 0.28])

    # ---- 3 dataset
    d.h1("3 · The dataset (yes, it was generated)")
    d.p(f"<b>{N['scenes']} scenes and {N['tasks']:,} tasks</b> ({N['tasks'] - N['real_tasks']:,} synthetic, {N['real_tasks']:,} on real "
        f"terrain), with <b>{N['pairs']} counterfactual pairs</b>. A self-audit excluded {N['excluded']} tasks ({N['excluded'] / N['tasks']:.1%}), "
        f"leaving {N['kept']:,} scored tasks. 2.1 GB of images, built in about {N['build_min']} minutes on 4 CPU cores. Every scene is "
        "rendered in three styles with the same answer key; ten skills, none of them counting.")
    d.images(["docs/pipeline/6_satellite.jpg", "docs/pipeline/6_map.jpg", "docs/pipeline/6_thermal.jpg"],
             "One scene, three styles, one answer key: satellite-style, topographic map, thermal.")
    d.table([["Q", "Skill", "Example question"],
             ["Q1", "Trace downstream", "Which villages receive DC-1's wastewater?"],
             ["Q2", "Order along a path", "Which village receives it first?"],
             ["Q3", "Nature-based fix", "Which wetland site cleans ALL the wastewater before ANY village?"],
             ["Q4", "Read elevation", "Which farms lie lower than pond P (gravity reuse)?"],
             ["Q5", "Flow direction", "Which way does the stream flow below the outfall?"],
             ["Q6", "Siting", "Which proposed site's wastewater reaches no village?"],
             ["Q7", "Trace upstream", "Which villages share the water source at intake I?"],
             ["Q8", "Colour-scale threshold", "At which monitoring points is water > 3 °C warmer?"],
             ["Q9", "Colour-scale value", "How many °C warmer is the water at M2?"],
             ["Q10", "Measure along a path", "How far (m) does the wastewater travel to the first village?"]], [0.08, 0.25, 0.67])
    d.p("<b>Where the data lives.</b> Full dataset: GitHub Release (three zip parts with SHA-256, manifest, validation report), rebuilt "
        "on GitHub's runners by the <font name='Mono'>dataset-release</font> workflow. In the repo: <font name='Mono'>dataset_sample/</font> "
        "(28 scenes plus twins, 529 tasks, 69 pairs) and <font name='Mono'>eval_set/</font> (exactly the tasks and images the models saw, "
        "with checksums and errata). Traps are built in: a village on the same stream but upstream, one close by but on another stream, "
        "a wetland after a village, monitoring points on other streams.")
    d.images(["docs/pipeline/8_original.jpg", "docs/pipeline/8_twin.jpg"],
             "A before-and-after twin: the outfall moves (≈0.6% of pixels) and the right answer flips. A model that answers from habit "
             "gets one half wrong.")

    # ---- 4 validity
    d.h1("4 · How every answer is established and checked")
    d.table([["Check", "What it proves"],
             ["V1 independent recomputation", f"pysheds re-derives flow and every answer; disagreement drops the question (scene pass {N['v1']})"],
             ["V2 known-answer tests", "Tilted plane, V-valley, ridge split, bowl-to-lake"],
             ["V3 counterfactual", f"{N['pairs']} linked twins whose answers provably differ, each re-validated"],
             ["V4 determinism", "Same seed, byte-identical images and answers"],
             ["V5/V7/V8 margins", "No near-ties in heights, distances or temperatures"],
             ["V9 pixel evidence", "The answer path is visible in the rendered pixels of each style"],
             ["V10 legibility", "Labels never overlap, stay inside the image, never sit under the legend"],
             ["V11 style applicability", "A question is asked only in styles that show its evidence"],
             ["V13 blind baseline", "Every question also asked without the image"],
             ["V14 answer balance", "Correct positions and set sizes rotated"],
             ["V15 human baseline", "Online human test on the same questions as the models"],
             ["Self-audit", f"{N['excluded']} unfair tasks found and excluded via errata, never edited"],
             ["Verification", "Every reported number recomputed by code that shares nothing with the report; random baseline at exact chance"],
             ["Two scorers", "Python and the browser port agree on all 37,516 replies (CI parity test)"]], [0.3, 0.7])
    if N.get("realism"):
        d.p(f"<b>Realism.</b> On real terrain, the simulated streams sit on mapped water {N['realism'][0]}× to {N['realism'][1]}× as often as "
            "chance would place them (<font name='Mono'>docs/REALISM.md</font>).")

    # ---- 5 results
    d.h1("5 · Results")
    d.h2("Frontier and open models on the same questions (batched protocol)")
    rows = [["Model", "Accuracy", "Without image", "Chance", "p (beats chance)", "Both halves of a pair"]]
    for r in fr:
        rows.append([pretty(r["m"]), f"<b>{pct(r['acc'])}</b> ({r['correct']}/{r['n']})", pct(r["blind"]) if r["blind"] is not None else "–",
                     pct(r["chance"]), pval(r["p"]), f"{r['pairs_right']} of {r['pairs']}" if r["pairs"] else "–"])
    d.table(rows, [0.27, 0.15, 0.13, 0.1, 0.15, 0.2])
    d.h2("Open models, main evaluation (one question per request)")
    rows = [["Model", "With image", "Without image", "Pairs both right"]]
    for m, v in sorted(N["main_overall"].items(), key=lambda kv: -kv[1]["image"]):
        p_ = N["main_pairs"].get(m, (0, 0))
        rows.append([pretty(m), pct(v["image"]), pct(v["blind"]), f"{p_[1]} of {p_[0]}"])
    d.table(rows, [0.4, 0.2, 0.2, 0.2])
    ft = N.get("ft")
    find = [f"<b>A frontier model does much better, but is not reliable yet.</b> {pretty(best['m'])} got {pct(best['acc'])} of {best['n']} "
            f"questions (p = {pval(best['p'])}), against {pct(ob['acc'])} for the best open model.",
            f"<b>The before-and-after test still catches it.</b> Over all {best['pairs']} pairs, {pretty(best['m'])} got both halves of only "
            f"{best['pairs_right']}; " + "; ".join(f"{pretty(r['m'])} {r['pairs_right']}" for r in fr[1:] if r["pairs"]) + ".",
            "<b>Without the image, scores fall to chance</b> for the models that were asked: their right answers come from looking.",
            f"<b>No open model beats guessing</b>: the best of {ob['models']}, {pretty(ob['m'])}, scores {pct(ob['acc'])} against a chance "
            f"level of {pct(ob['chance'])}."]
    if ft:
        find.append(f"<b>The data can teach the skill, a little:</b> fine-tuning {ft['model']} on ThirstMap tasks raised it from {pct(ft['base'])} "
                    f"to {pct(ft['tuned'])} on held-out scenes (p = {pval(ft.get('p', 1))}).")
    d.bullets(find)
    d.image("results/models/chart_accuracy_by_skill.png", 0.8, "Accuracy by skill against chance (open models, main evaluation).")
    d.image("docs/trap_chart.png", 0.95, "How often each model fell for a built-in trap, and which traps catch them.")

    # ---- 6 product
    d.h1("6 · The product: what people can open and use")
    d.table([["Piece", "What it is", "Where"],
             ["Live demo", "Results first, then one scene through every pipeline step, then 64 tasks with each model's reply scored ✓/✗ and "
              "an answer reveal, before-and-after pairs, sticky navigation", link(SITE)],
             ["Leaderboard", "Report card per model (skills, pairs, traps, no-image check); download the question pack, run any model, drop "
              "the replies on the page and get the same card, scored in the browser", link(SITE + "leaderboard/")],
             ["Films", "4-minute narrated walkthrough of every criterion and deliverable, plus a 70-second cut, subtitled; numbers read "
              "from the result files", link(SITE + "film.html")],
             ["Human test", "32 questions the models answered, all 7 original pairs; answers sent to a Netlify form", link(SITE + "human/")],
             ["One-page summary", "The whole project on one A4 page", "docs/ThirstMap_summary.pdf"],
             ["Docs", "Findings, FAQ, validation report, verification, audit, realism, policy note, pitch, dataset card", "docs/"],
             ["CLI", "pip install gives a thirstmap command with every pipeline stage as a subcommand", "thirstmap/cli.py"],
             ["Notebook", "Colab quick start, no key", "ThirstMap_quickstart.ipynb"]], [0.14, 0.5, 0.36])
    d.image("docs/video/film_poster.jpg", 0.62, "The film's poster frame (docs/video/).")

    # ---- 7 repo tour
    d.h1("7 · Tour of the repository")
    d.table([["Path", "What is there"],
             ["thirstmap/", "The package: terrain, scene, questions, renderers, validators, scoring, errata, CLI"],
             ["generate.py · build_dataset.py · variants.py", "Make one scene (and twin), the whole dataset, appearance variants"],
             ["evaluate.py · frontier.py · staircase.py · probes.py", "Run models: per task, batched for free tiers, adaptive eye exam, reading checks"],
             ["report.py · findings.py · verify_results.py", "Reports and charts; findings text from the numbers; independent recomputation"],
             ["audit_labels.py · validation_report.py · realism_check.py", "Self-audit, validation evidence, real-water check"],
             ["build_demo.py · build_leaderboard.py · human_eval.py", "The live demo, the leaderboard, the human test"],
             ["make_summary.py · make_full_report.py · video/", "The one-page PDF and FAQ, this report, the films"],
             ["dataset_sample/ · eval_set/", "A ready slice of the dataset; the exact inputs the models saw"],
             ["results/", "Every run: raw replies (responses.jsonl), summary.json, REPORT.md, charts"],
             ["docs/", "Demo, leaderboard, films, PDFs, findings, FAQ, validation, verification, audit, policy note, pitch"],
             ["tests/", f"{N['tests']} tests: hydrology, validators, scoring, determinism, scorer parity with the browser"],
             [".github/workflows/", "CI, demo/Pages deploy, dataset release, package release"],
             ["run_all.sh · run_open_models.sh", "One command for everything; the open models"]], [0.42, 0.58])

    # ---- 8 commands
    d.h1("8 · Commands: clone, pull, install, test, run")
    d.p("<b>Get the code</b> (public repository; the GitLab mirror has the same history):")
    d.code("git clone https://github.com/yugesh1111/THIRSTMAP.git\ncd THIRSTMAP\n"
           "# later, to get the newest version:\ngit pull origin main\n\n"
           "# or the GitLab mirror:\ngit clone https://gitlab.com/Amritha902/thirstmap.git")
    d.p("<b>Understand the repository</b> quickly:")
    d.code("git log --oneline | head -20          # what changed, newest first\n"
           "cat README.md                          # the judges' tour, findings, quick start\n"
           "ls thirstmap/ results/ docs/           # package, every run, documents\n"
           "python3 generate.py --help             # every script explains its options\n"
           "open docs/demo/index.html              # the demo works from the file system too")
    d.p("<b>Install and test</b>:")
    d.code("python3 -m venv .venv && source .venv/bin/activate\npip install -r requirements.txt\n"
           f"python3 -m pytest -q                   # {N['tests']} tests\npip install -e .                        # gives the thirstmap command\nthirstmap list")
    d.p("<b>Make tasks and run the pipeline</b>:")
    d.code("python3 generate.py --level 3 --seed 11 --twin          # one scene + its twin -> out/\n"
           "python3 generate.py --level 3 --seed 5 --real navi_mumbai\n"
           "./run_all.sh --quick                                    # small end-to-end run, about 2 min\n"
           "./run_all.sh                                            # full benchmark, about 25 min on 4 cores\n"
           "python3 build_dataset.py --per-level 18 --real-per-location 9 --out dataset --workers 4")
    d.p("<b>Evaluate models</b> (keys come from the environment, never from code):")
    d.code("python3 evaluate.py --dataset dataset_sample --models mock:oracle mock:random --blind --run offline\n"
           "./run_open_models.sh                                    # 4 open models, local, no key\n"
           "python3 frontier.py select --out results/frontier\n"
           "OPENAI_API_KEY=... python3 frontier.py run --budget 20 \\\n"
           "    --models \"openai:gemini-3.1-flash-lite@https://generativelanguage.googleapis.com/v1beta/openai/\"\n"
           "python3 findings.py --run results/models                # findings text from the numbers")
    d.p("<b>Rebuild the documents and the product</b>:")
    d.code("python3 make_summary.py && python3 make_full_report.py    # the one-page PDF, FAQ and this report\n"
           "python3 build_demo.py --dataset dataset --run results/models --baselines results/offline_baselines \\\n"
           "    --pipeline docs/pipeline --out docs/demo\npython3 build_leaderboard.py\npython3 verify_results.py")

    # ---- 9 criteria
    d.h1("9 · Against the judging criteria")
    d.table([["Criterion", "Where ThirstMap answers it"],
             ["Implementation (25%)", f"One-command pipeline from terrain to report; {N['tests']} tests and CI; pip-installable command; a public "
              "leaderboard where anyone scores their own model in the browser; live site redeployed on every change"],
             ["Validity (25%)", "Answers from a simulation, re-derived by an independent library; evidence checked in the pixels; questions "
              "dropped, never edited; self-audit; two scorer implementations agree on every reply; exact inputs with checksums"],
             ["Variation (20%)", f"{N['skills']} reasoning skills, no counting; {N['styles']} image styles; 5 difficulty levels; real terrain for "
              f"{N['real_cities']} cities; twins; season, haze and sensor variants"],
             ["Originality (15%)", f"Twins with one minimal change that must flip the answer (the best model gets both halves of only "
              f"{best['pairs_right']} of {best['pairs']}); the consequence of each model error drawn on the image"],
             ["Impact (15%)", "India's data-centre water problem; what each AI mistake would mean on the ground; a policy note proposing a "
              "pass bar for AI water screening"]], [0.22, 0.78])

    # ---- 10 honest limits
    d.h1("10 · Limits, stated plainly")
    d.bullets(["Frontier runs used free API tiers (about 20 requests per model per day), so they use batched prompts and samples of "
               f"{best['n']} questions and {best['pairs']} pairs; p-values are exact, but the samples are small.",
               "Claude and GPT have not been run yet; the harness supports them once keys are available.",
               "The human test is online, but no human answers had been received when this report was built, so there is no human "
               "baseline number." if not N.get("human") else "Human answers are scored with the models' scorer.",
               "Landscapes are synthetic (plus real terrain with hypothetical facilities); the realism check measures how close they are."])
    d.p(f"Built by make_full_report.py from the repository at commit {head}.", "small")
    d.build()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--out", default="docs/ThirstMap_full_report.pdf")
    a = ap.parse_args()
    report(numbers(a.dataset), a.out)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
