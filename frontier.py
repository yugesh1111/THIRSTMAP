"""Frontier check under a tight request budget (e.g. a free API tier of 20 requests per model per day).

Token and request economy, applied together:
  * batch prompting: every question about one image goes in ONE request, answered as one JSON object
    (Cheng et al. 2023, "Batch Prompting: Efficient Inference with LLM APIs"), so one request scores ~5 tasks;
  * one-tile images: each image is resized so its longer side is <= 768 px, which Gemini bills as a single
    258-token tile instead of four (labels stay legible; the resized copies are kept for inspection);
  * a hard per-model request budget, failures included, and an immediate stop on a daily-quota error;
  * resume: an image a model already answered is never sent again.
The same batched prompts and images go to the open models, so the comparison is like for like.

Usage:
  python3 frontier.py select --dataset dataset --out results/frontier
  OPENAI_API_KEY=proxy-injected python3 frontier.py run --models \
      "openai:gemini-3.1-flash-lite@https://generativelanguage.googleapis.com/v1beta/openai/" --budget 20
  python3 frontier.py run --models hf:Qwen/Qwen2.5-VL-3B-Instruct
"""
import argparse
import json
import random
import re
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image

from report import build_report
from thirstmap.scoring import score

MAX_SIDE = 768


def image_key(t):
    return f"{t['scene_id']}__{t['style']}"


def select(a):
    ds, out = Path(a.dataset), Path(a.out)
    from thirstmap import errata
    bad = errata.load(ds)
    tasks = [t for t in map(json.loads, open(ds / "tasks.jsonl")) if t["task_id"] not in bad]
    by_img = defaultdict(list)
    for t in tasks:
        by_img[image_key(t)].append(t)
    rng = random.Random(a.seed)
    # pairs: base + twin images that both carry questions, one per (twin kind, style), most questions first
    pairs = defaultdict(list)
    for t in tasks:
        if t.get("variant") == "counterfactual":
            base = f"{t['scene_id'][:-3]}__{t['style']}"
            if base in by_img and len(by_img[base]) >= 2:
                pairs[(t["cf_kind"], t["style"])].append((base, image_key(t)))
    chosen, pools = [], {}
    for k in sorted(pairs):
        cand = sorted(set(pairs[k]))
        rng.shuffle(cand)
        pools[k] = sorted(cand[:20], key=lambda bc: -(len(by_img[bc[0]]) + len(by_img[bc[1]])))
    while len(chosen) < 2 * a.pairs and any(pools.values()):          # round-robin over twin kinds and styles
        for k in sorted(pools):
            if pools[k] and len(chosen) < 2 * a.pairs:
                chosen += list(pools[k].pop(0))
    # singles: images with many questions, spread across styles, levels and real terrain
    used = {c.split("__")[0].removesuffix("_cf") for c in chosen}
    singles = [k for k, v in by_img.items() if not v[0].get("variant") == "counterfactual"
               and v[0]["scene_id"] not in used and len(v) >= (2 if v[0]["style"] == "thermal" else 3)]
    rng.shuffle(singles)
    want = [("satellite", "synthetic"), ("map", "synthetic"), ("satellite", "real"), ("map", "real"),
            ("thermal", "synthetic"), ("map", "synthetic")]
    for style, terrain in want[: a.singles]:
        pick = next((k for k in singles if k.endswith("__" + style) and k not in chosen
                     and (by_img[k][0].get("terrain", "synthetic") == "synthetic") == (terrain == "synthetic")), None)
        if pick:
            chosen.append(pick)
    (out / "img").mkdir(parents=True, exist_ok=True)
    images = []
    for k in chosen:
        ts = sorted(by_img[k], key=lambda t: int(t["qid"][1:]))
        im = Image.open(ds / ts[0]["image"]).convert("RGB")
        s = MAX_SIDE / max(im.size)
        if s < 1:
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        im.save(out / "img" / f"{k}.png", optimize=True)
        images.append(dict(image=k, file=f"img/{k}.png", size=im.size, tasks=[t["task_id"] for t in ts]))
    (out / "set.json").write_text(json.dumps(dict(max_side=MAX_SIDE, images=images), indent=1))
    n = sum(len(i["tasks"]) for i in images)
    print(f"{len(images)} images, {n} questions ({n / len(images):.1f} per request) -> {out / 'set.json'}")


def batch_prompt(ts):
    head = ts[0]["prompt"].split("Question:")[0].strip()
    lines = [head, "", "Answer EVERY question below about this image."]
    for t in ts:
        fmt = t["prompt"].split("where the answer is", 1)[-1].strip().rstrip(".")
        lines.append(f"{t['qid']}: {t['question']} (answer: {fmt})")
    keys = ", ".join(f'"{t["qid"]}": ...' for t in ts)
    lines += ["", f"Look carefully at the image. Reply with ONLY one JSON object: {{{keys}}}"]
    return "\n".join(lines)


def parse_batch(raw):
    for m in reversed(list(re.finditer(r"\{.*\}", raw or "", re.S))):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return {}


def make(spec, root):
    if spec.startswith("hf:"):
        from thirstmap.models import HFVisionAdapter
        return HFVisionAdapter(spec[3:], root=root, max_new_tokens=320)
    from thirstmap.models import make_adapter
    ad = make_adapter(spec, root=root)
    if hasattr(ad, "client"):
        ad.client = ad.client.with_options(max_retries=3)     # do not burn a daily quota on retries
    return ad


def run(a):
    ds, out = Path(a.dataset), Path(a.out)
    S = json.loads((out / "set.json").read_text())
    tasks = {json.loads(l)["task_id"]: json.loads(l) for l in open(ds / "tasks.jsonl")}
    resp, reqs = out / "responses.jsonl", out / "requests.jsonl"
    mode = "blind" if a.blind else "image"
    for spec in a.models:
        ad = make(spec, out)
        done = set()
        if reqs.exists():
            done = {r["image"] for r in map(json.loads, open(reqs))
                    if r["model"] == ad.name and not r.get("error") and r.get("mode", "image") == mode}
        sent = 0
        for img in S["images"]:
            if img["image"] in done:
                continue
            if sent >= a.budget:
                print(f"{ad.name}: request budget {a.budget} reached")
                break
            ts = [tasks[i] for i in img["tasks"]]
            pseudo = dict(prompt=batch_prompt(ts), image=img["file"])
            sent += 1
            t0 = time.time()
            try:
                r = ad.ask(pseudo, with_image=not a.blind)
            except Exception as e:                                   # noqa: BLE001 (recorded, then continue)
                msg = str(getattr(e, "body", e))
                with open(reqs, "a") as f:
                    f.write(json.dumps(dict(model=ad.name, image=img["image"], mode=mode, error=f"{type(e).__name__}: {msg[:300]}",
                                            latency_s=round(time.time() - t0, 1))) + "\n")
                print(f"{ad.name} {img['image']}: {type(e).__name__}")
                if "per day" in msg or "PerDay" in msg:
                    print(f"{ad.name}: daily quota used up, stopping this model")
                    break
                continue
            obj = parse_batch(r["raw"])
            with open(reqs, "a") as f:
                f.write(json.dumps(dict(model=ad.name, image=img["image"], mode=mode, raw=r["raw"], served_model=r.get("served_model"),
                                        input_tokens=r.get("input_tokens"), output_tokens=r.get("output_tokens"),
                                        latency_s=r.get("latency_s"), questions=len(ts))) + "\n")
            with open(resp, "a") as f:
                for t in ts:
                    raw = json.dumps({"answer": obj[t["qid"]]}) if t["qid"] in obj else ""
                    f.write(json.dumps(dict(model=ad.name, mode=mode, task_id=t["task_id"], raw=raw,
                                            protocol="batched", latency_s=r.get("latency_s"), **score(t, raw)),
                                       default=str) + "\n")
            got = sum(score(t, json.dumps({"answer": obj.get(t["qid"])}))["correct"] for t in ts if t["qid"] in obj)
            print(f"{ad.name} {img['image']}: {got}/{len(ts)} right, {r.get('input_tokens')} in / "
                  f"{r.get('output_tokens')} out tokens, {r.get('latency_s')} s", flush=True)
    build_report(out, ds)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--dataset", default="dataset"); s.add_argument("--out", default="results/frontier")
    s.add_argument("--pairs", type=int, default=6); s.add_argument("--singles", type=int, default=6)
    s.add_argument("--seed", type=int, default=0)
    r = sub.add_parser("run")
    r.add_argument("--dataset", default="dataset"); r.add_argument("--out", default="results/frontier")
    r.add_argument("--models", nargs="+", required=True)
    r.add_argument("--budget", type=int, default=20, help="max requests per model in this call, failures included")
    r.add_argument("--blind", action="store_true", help="control: the same batched questions WITHOUT the image")
    a = ap.parse_args()
    select(a) if a.cmd == "select" else run(a)


if __name__ == "__main__":
    main()
