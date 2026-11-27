"""`thirstmap` command: one entry point for the whole pipeline.

    thirstmap generate --level 3 --seed 11 --twin --out out      one scene (+ twin): images, questions, answer key
    thirstmap build --per-level 18 --out dataset --workers 4     a full dataset with manifest
    thirstmap evaluate --dataset dataset --models mock:random --run test
    thirstmap report results/test --dataset dataset
    thirstmap frontier run --models hf:Qwen/Qwen2.5-VL-3B-Instruct
    thirstmap human score "answers/*.txt" --dataset eval_set --run results/frontier
    thirstmap list                                               every command

Each command runs the matching pipeline script with the remaining arguments (`thirstmap generate --help`).
"""
import runpy
import sys
from pathlib import Path

COMMANDS = {
    "generate": ("generate", "one scene (and its twin): images, questions, answer key"),
    "build": ("build_dataset", "a full dataset, in parallel, with manifest"),
    "probes": ("probes", "reading checks (can the model read the labels?)"),
    "variants": ("variants", "monsoon / haze / coarse-sensor versions of scenes"),
    "evaluate": ("evaluate", "ask models the questions, with and without the image"),
    "frontier": ("frontier", "frontier check under a request budget (batched prompts)"),
    "staircase": ("staircase", "adaptive eye exam: breaking level per skill"),
    "trace": ("trace_task", "draw the water's path: models trace the route, scored cell by cell"),
    "cloud": ("cloud_task", "can't-tell tasks: a cloud hides the deciding stretch, proved unanswerable"),
    "beyond": ("beyond_answers", "the route and honesty checks: page, README block, figures"),
    "finetune": ("finetune", "LoRA fine-tune a small open model on held-out scenes"),
    "report": ("report", "metrics, charts and REPORT.md for a results run"),
    "findings": ("findings", "docs/FINDINGS.md, LEADERBOARD.md and the README findings"),
    "overlays": ("overlays", "model answers drawn on the images, error consequences"),
    "human": ("human_eval", "human test page (build) and scorer (score)"),
    "verify": ("verify_results", "independent recomputation and byte-for-byte rebuilds"),
    "audit": ("audit_labels", "dataset audit (hidden labels, malformed scenes)"),
    "realism": ("realism_check", "simulated streams vs real surface water"),
    "validation-report": ("validation_report", "all validation evidence in one document"),
    "eval-set": ("publish_eval_set", "copy exactly the evaluated tasks and images"),
    "demo": ("build_demo", "the self-contained demo page"),
    "summary": ("make_summary", "one-page summary PDF and the FAQ, from the result files"),
    "leaderboard": ("build_leaderboard", "leaderboard page: report cards, question pack, score your model in the browser"),
    "pipeline": ("pipeline_visuals", "one scene through every pipeline step"),
    "gifs": ("make_gifs", "the README GIFs"),
}


def tools_dir():
    """Where the pipeline scripts live: the installed `thirstmap_tools` package, or the repository root."""
    try:
        import thirstmap_tools
        for d in thirstmap_tools.__path__:
            if (Path(d) / "generate.py").exists():
                return Path(d)
    except ImportError:
        pass
    root = Path(__file__).resolve().parent.parent
    if (root / "generate.py").exists():
        return root
    sys.exit("thirstmap: pipeline scripts not found; reinstall it (README, Quick start: Install it as a command)")


def usage():
    width = max(map(len, COMMANDS))
    lines = ["usage: thirstmap <command> [options]   (thirstmap <command> --help for its options)", "", "commands:"]
    lines += [f"  {name.ljust(width)}  {desc}" for name, (_, desc) in COMMANDS.items()]
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help", "list"):
        print(usage())
        return 0
    cmd = argv[0]
    if cmd not in COMMANDS:
        print(f"thirstmap: unknown command '{cmd}'\n\n{usage()}", file=sys.stderr)
        return 2
    script = tools_dir() / f"{COMMANDS[cmd][0]}.py"
    sys.path.insert(0, str(script.parent))           # the scripts import each other by plain name
    sys.argv = [f"thirstmap {cmd}"] + argv[1:]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
