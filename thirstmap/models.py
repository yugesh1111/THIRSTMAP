"""Model adapters. Each one answers a task (image + prompt) and reports tokens and latency.

API keys are read from the environment by each SDK, never from code:
  Claude  : ANTHROPIC_API_KEY (or an `ant auth login` profile)
  OpenAI-compatible : OPENAI_API_KEY (+ optional base URL, e.g. an organiser-provided endpoint)
  Gemini  : GEMINI_API_KEY / GOOGLE_API_KEY
The OpenAI-compatible and Gemini adapters are provided for organiser-supplied access and were not
exercised in the build environment (no keys there); the mock adapters run offline.
"""
import base64
import json
import random
import time
from pathlib import Path

# Anthropic first-party list prices, USD per million tokens (input, output). Others: pass --prices.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-fable-5-2": (8.00, 40.00),
}

BLIND_NOTE = ("\n\n(The image is NOT available to you for this question. Give your best guess "
              "in the required format anyway.)")


def _png_b64(path):
    return base64.standard_b64encode(Path(path).read_bytes()).decode("ascii")


def _prompt(task, with_image):
    return task["prompt"] if with_image else task["prompt"] + BLIND_NOTE


class ClaudeAdapter:
    """Claude via the official Anthropic SDK (Messages API).

    Server-side refusal fallbacks are OFF by default here on purpose: in a benchmark the answer must
    come from the model being measured. Pass fallbacks=True to enable them; the served model is
    recorded either way.
    """

    def __init__(self, model="claude-opus-5-5", effort=None, fallbacks=False, root="."):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model, self.effort, self.fallbacks, self.root = model, effort, fallbacks, Path(root)
        self.name = f"claude:{model}" + (f"@{effort}" if effort else "")

    def ask(self, task, with_image=True):
        content = []
        if with_image:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                        "data": _png_b64(self.root / task["image"])}})
        content.append({"type": "text", "text": _prompt(task, with_image)})
        kwargs = dict(model=self.model, max_tokens=16000, messages=[{"role": "user", "content": content}])
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        t0 = time.time()
        if self.fallbacks:
            resp = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                    fallbacks="default", **kwargs)
        else:
            resp = self.client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if b.type == "text")
        return dict(raw=text, stop_reason=resp.stop_reason, served_model=resp.model,
                    input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
                    latency_s=round(time.time() - t0, 2))


class OpenAICompatAdapter:
    """Any OpenAI-compatible chat-completions endpoint (official SDK `openai`)."""

    def __init__(self, model, base_url=None, root="."):
        from openai import OpenAI
        # busy public endpoints answer 429 / 503 under load: retry with backoff instead of recording an error
        kw = dict(max_retries=8, timeout=600)
        self.client = OpenAI(base_url=base_url, **kw) if base_url else OpenAI(**kw)
        self.model, self.root = model, Path(root)
        self.name = f"openai:{model}"

    def ask(self, task, with_image=True):
        content = [{"type": "text", "text": _prompt(task, with_image)}]
        if with_image:
            url = f"data:image/png;base64,{_png_b64(self.root / task['image'])}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        t0 = time.time()
        resp = self.client.chat.completions.create(model=self.model,
                                                   messages=[{"role": "user", "content": content}])
        u = resp.usage
        return dict(raw=resp.choices[0].message.content or "", stop_reason=resp.choices[0].finish_reason,
                    served_model=resp.model, input_tokens=getattr(u, "prompt_tokens", None),
                    output_tokens=getattr(u, "completion_tokens", None), latency_s=round(time.time() - t0, 2))


class GeminiAdapter:
    """Gemini via the official `google-genai` SDK."""

    def __init__(self, model, root="."):
        from google import genai
        self.client = genai.Client()
        self.model, self.root = model, Path(root)
        self.name = f"gemini:{model}"

    def ask(self, task, with_image=True):
        from google.genai import types
        parts = []
        if with_image:
            parts.append(types.Part.from_bytes(data=(self.root / task["image"]).read_bytes(), mime_type="image/png"))
        parts.append(_prompt(task, with_image))
        t0 = time.time()
        resp = self.client.models.generate_content(model=self.model, contents=parts)
        um = resp.usage_metadata
        return dict(raw=resp.text or "", stop_reason=None, served_model=self.model,
                    input_tokens=getattr(um, "prompt_token_count", None),
                    output_tokens=getattr(um, "candidates_token_count", None), latency_s=round(time.time() - t0, 2))


class HFVisionAdapter:
    """Open-weight vision-language model from Hugging Face, run locally with `transformers`.

    No API key needed; runs on CPU (slow) or GPU. `max_side` downsizes the image's longer side
    before encoding to bound cost on CPU (recorded in the model name so runs are comparable).
    """

    def __init__(self, model_id, root=".", max_side=None, dtype=None, max_new_tokens=48):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.torch = torch
        dt = dtype or (torch.bfloat16 if any(k in model_id.lower() for k in ("3b", "7b", "2b")) else torch.float32)
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForImageTextToText.from_pretrained(model_id, dtype=dt).eval()
        self.root, self.max_side, self.max_new_tokens = Path(root), max_side, max_new_tokens
        self.name = f"hf:{model_id}" + (f"@{max_side}px" if max_side else "")

    def _image(self, path):
        from PIL import Image
        im = Image.open(path).convert("RGB")
        if self.max_side and max(im.size) > self.max_side:
            s = self.max_side / max(im.size)
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        return im

    def ask(self, task, with_image=True):
        content = []
        if with_image:
            content.append({"type": "image", "image": self._image(self.root / task["image"])})
        content.append({"type": "text", "text": _prompt(task, with_image)})
        msgs = [{"role": "user", "content": content}]
        inputs = self.processor.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                                    return_dict=True, return_tensors="pt")
        t0 = time.time()
        with self.torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        n_in = inputs["input_ids"].shape[1]
        text = self.processor.decode(out[0][n_in:], skip_special_tokens=True)
        return dict(raw=text, stop_reason=None, served_model=self.name, input_tokens=int(n_in),
                    output_tokens=int(out.shape[1] - n_in), latency_s=round(time.time() - t0, 2))


class MockAdapter:
    """Offline baselines.

    oracle   : always returns the reference answer (proves scoring accepts correct answers)
    random   : a uniformly random valid answer (chance level for every question type)
    stubborn : answers every counterfactual twin with its BASE scene's answer, i.e. a model that
               ignores the change. Perfect on single tasks, so only the pair metric exposes it.
    """

    def __init__(self, kind):
        assert kind in ("oracle", "random", "stubborn")
        self.kind, self.name = kind, f"mock:{kind}"

    def ask(self, task, with_image=True):
        if self.kind == "oracle":
            ans = task["answer"]
        elif self.kind == "stubborn":
            ans = task.get("pair_answer", task["answer"])
        else:
            rng = random.Random(task["task_id"] + str(with_image))
            opts, sc = task["options"], task["scoring"]
            if sc == "set":
                ans = sorted(o for o in opts if rng.random() < 0.35)
            elif sc == "number":
                ans = round(rng.uniform(*opts), 1)
            else:
                ans = rng.choice(opts)
        return dict(raw=json.dumps({"answer": ans}), stop_reason="end_turn", served_model=self.name,
                    input_tokens=0, output_tokens=0, latency_s=0.0)


def make_adapter(spec, root="."):
    """spec examples: claude:claude-opus-5-5  claude:claude-sonnet-5-5@low  openai:MODEL
    openai:MODEL@https://host/v1  gemini:MODEL  hf:HF_MODEL_ID[@MAXSIDEpx]  mock:oracle  mock:random"""
    kind, _, rest = spec.partition(":")
    if kind == "claude":
        model, _, effort = rest.partition("@")
        return ClaudeAdapter(model or "claude-opus-5-5", effort or None, root=root)
    if kind == "openai":
        model, _, base = rest.partition("@")
        return OpenAICompatAdapter(model, base or None, root=root)
    if kind == "gemini":
        return GeminiAdapter(rest, root=root)
    if kind == "hf":
        model, _, side = rest.partition("@")
        return HFVisionAdapter(model, root=root, max_side=int(side.rstrip("px")) if side else None)
    if kind == "mock":
        return MockAdapter(rest)
    raise ValueError(f"unknown model spec {spec}")


def cost_usd(model_name, input_tokens, output_tokens, extra_prices=None):
    prices = dict(PRICES, **(extra_prices or {}))
    key = model_name.split(":", 1)[-1].split("@")[0]
    if key not in prices or input_tokens is None or output_tokens is None:
        return None
    pin, pout = prices[key]
    return round((input_tokens * pin + output_tokens * pout) / 1e6, 6)
