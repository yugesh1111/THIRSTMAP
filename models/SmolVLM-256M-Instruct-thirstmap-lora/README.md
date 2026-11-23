---
base_model: HuggingFaceTB/SmolVLM-256M-Instruct
library_name: peft
tags:
- base_model:adapter:HuggingFaceTB/SmolVLM-256M-Instruct
- lora
- transformers
- thirstmap
---

# SmolVLM-256M + ThirstMap LoRA adapter

A small research adapter that tests one question: **can the ThirstMap dataset teach a vision-language model to
trace water through terrain images?** It is not a production model.

- **Base model:** [HuggingFaceTB/SmolVLM-256M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct)
- **Method:** LoRA (r = 16, alpha = 32, dropout 0.05) on the attention and MLP projections; loss on the answer tokens only
- **Training data:** 300 ThirstMap tasks (30 per question type) from scenes that never appear in the test set;
  2 epochs on CPU, images resized to 512 px, no image tiling. Settings are in `TRAINING.json`.
- **Test:** 168 questions from 108 held-out scene families, asked with and without the image, for the base model
  and for this adapter. Results and the no-image control: [`docs/FINDINGS.md`](../../docs/FINDINGS.md) and
  [`results/finetune/REPORT.md`](../../results/finetune/REPORT.md).

## Use

```python
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoProcessor

base = AutoModelForImageTextToText.from_pretrained("HuggingFaceTB/SmolVLM-256M-Instruct")
model = PeftModel.from_pretrained(base, "models/SmolVLM-256M-Instruct-thirstmap-lora").eval()
processor = AutoProcessor.from_pretrained("HuggingFaceTB/SmolVLM-256M-Instruct")
processor.image_processor.do_image_splitting = False   # as in training
```

Reproduce: `python3 finetune.py --test-run results/open_models --train-per-q 30 --epochs 2 --blind`

## Limits

Trained on a few hundred synthetic examples on CPU. Images are synthetic renders; nothing here should be used to
judge real facilities or real water flows.
