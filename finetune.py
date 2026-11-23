"""Can the dataset TEACH the skill? LoRA fine-tune a small open VLM, test on held-out scenes.

Train: tasks from scenes that never appear in the test set (and not their twins).
Test : the same held-out tasks for the base model and the fine-tuned model, same image size.
Runs on CPU at small scale (a few hundred examples); results are reported honestly as such.

Usage:
  python3 finetune.py --test-run results/open_models --train-per-q 40 --epochs 1
  -> models/<name>-thirstmap-lora/ (adapter), results/finetune/ (responses + REPORT.md)
"""
import argparse
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import torch
from PIL import Image

from report import build_report
from thirstmap.models import BLIND_NOTE  # noqa: F401  (same prompt format as evaluation)
from thirstmap.scoring import score


def scene_family(scene_id):
    return scene_id[:-3] if scene_id.endswith("_cf") else scene_id


def load_image(path, max_side):
    im = Image.open(path).convert("RGB")
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    return im


def encode(processor, image, prompt, answer=None):
    msgs = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
    if answer is None:
        return processor.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                             return_dict=True, return_tensors="pt")
    full = msgs + [{"role": "assistant", "content": [{"type": "text", "text": json.dumps({"answer": answer})}]}]
    enc = processor.apply_chat_template(full, tokenize=True, return_dict=True, return_tensors="pt")
    n_prompt = processor.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                             return_dict=True, return_tensors="pt")["input_ids"].shape[1]
    labels = enc["input_ids"].clone()
    labels[:, :n_prompt] = -100                      # learn only the answer tokens
    enc["labels"] = labels
    return enc


def generate(model, processor, image, prompt):
    enc = encode(processor, image, prompt)
    with torch.inference_mode():
        out = model.generate(**enc, max_new_tokens=40, do_sample=False)
    return processor.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--model", default="HuggingFaceTB/SmolVLM-256M-Instruct")
    ap.add_argument("--test-run", default="results/open_models", help="run whose image tasks form the test set")
    ap.add_argument("--train-per-q", type=int, default=40)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--max-side", type=int, default=512)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--out", default="results/finetune")
    ap.add_argument("--split-images", action="store_true",
                    help="let the processor tile each image (more tokens, much slower on CPU)")
    a = ap.parse_args()
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText, AutoProcessor
    torch.manual_seed(0)
    ds = Path(a.dataset).resolve()
    tasks = {}
    for f in ("tasks.jsonl",):
        for line in open(ds / f):
            t = json.loads(line)
            tasks[t["task_id"]] = t
    test_ids = sorted({json.loads(l)["task_id"] for l in open(Path(a.test_run) / "responses.jsonl")
                       if json.loads(l)["task_id"] in tasks and json.loads(l)["mode"] == "image"})
    test = [tasks[i] for i in test_ids]
    held_out = {scene_family(t["scene_id"]) for t in test}
    pool = defaultdict(list)
    for t in tasks.values():
        if scene_family(t["scene_id"]) not in held_out:
            pool[t["qid"]].append(t)
    rng = random.Random(0)
    train = [t for q in sorted(pool) for t in rng.sample(pool[q], min(a.train_per_q, len(pool[q])))]
    rng.shuffle(train)
    print(f"train {len(train)} tasks from {len({t['scene_id'] for t in train})} scenes | "
          f"test {len(test)} tasks from {len(held_out)} held-out scene families (no overlap)", flush=True)

    processor = AutoProcessor.from_pretrained(a.model)
    if not a.split_images and hasattr(processor.image_processor, "do_image_splitting"):
        processor.image_processor.do_image_splitting = False   # one view per image: ~6x fewer tokens
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    resp = out / "responses.jsonl"
    short = a.model.split("/")[-1]

    def evaluate(model, name):
        model.eval()
        done = set()
        if resp.exists():
            done = {json.loads(l)["task_id"] for l in open(resp) if json.loads(l)["model"] == name}
        for k, t in enumerate(test):
            if t["task_id"] in done:
                continue
            t0 = time.time()
            raw = generate(model, processor, load_image(ds / t["image"], a.max_side), t["prompt"])
            rec = dict(model=name, mode="image", task_id=t["task_id"], raw=raw, latency_s=round(time.time() - t0, 2),
                       input_tokens=None, output_tokens=None, cost_usd=None, **score(t, raw))
            with open(resp, "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
            if (k + 1) % 25 == 0:
                print(f"  {name}: {k + 1}/{len(test)}", flush=True)

    base = AutoModelForImageTextToText.from_pretrained(a.model, dtype=torch.float32)
    evaluate(base, f"hf:{short}@{a.max_side}px (base)")

    cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(base, cfg)
    model.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr)
    accum, step, t0 = 8, 0, time.time()
    model.train()
    for ep in range(a.epochs):
        for k, t in enumerate(train):
            enc = encode(processor, load_image(ds / t["image"], a.max_side), t["prompt"], t["answer"])
            loss = model(**enc).loss / accum
            loss.backward()
            if (k + 1) % accum == 0:
                opt.step(); opt.zero_grad(); step += 1
                if step % 5 == 0:
                    print(f"  epoch {ep + 1} step {step} loss {loss.item() * accum:.3f} "
                          f"({time.time() - t0:.0f}s)", flush=True)
    adapter_dir = Path("models") / f"{short}-thirstmap-lora"
    model.save_pretrained(adapter_dir)
    (adapter_dir / "TRAINING.json").write_text(json.dumps(dict(
        base_model=a.model, train_tasks=len(train), epochs=a.epochs, lr=a.lr, max_side=a.max_side,
        image_splitting=a.split_images,
        lora=dict(r=16, alpha=32), held_out_scene_families=len(held_out), train_seconds=round(time.time() - t0)),
        indent=2))
    evaluate(model, f"hf:{short}@{a.max_side}px (fine-tuned on ThirstMap)")
    build_report(out, ds)


if __name__ == "__main__":
    main()
