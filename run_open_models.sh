#!/usr/bin/env bash
# Evaluate free, open-weight vision-language models from Hugging Face on the benchmark.
# No API keys needed; runs on CPU (about 10-15 s per task on 4 cores) or GPU.
# Every model gets the SAME tasks: one per (question, style, difficulty) cell, 30 counterfactual
# pairs and 4 perception probes per (probe, style); each also asked WITHOUT the image (--blind).
#   ./run_open_models.sh                 # all models below, results in results/models/
#   MODELS="Qwen/Qwen2.5-VL-3B-Instruct" ./run_open_models.sh
set -uo pipefail
cd "$(dirname "$0")"
export HF_HUB_DISABLE_XET=1
RUN="${RUN:-models}"
MODELS="${MODELS:-Qwen/Qwen2.5-VL-3B-Instruct Qwen/Qwen2-VL-2B-Instruct HuggingFaceTB/SmolVLM2-2.2B-Instruct HuggingFaceTB/SmolVLM-256M-Instruct}"
[ -f dataset/probes.jsonl ] || python3 probes.py --dataset dataset
for ID in $MODELS; do
  echo "== $ID  $(date -u +%H:%M:%S)"
  python3 -c "from huggingface_hub import snapshot_download as s; s('$ID', allow_patterns=['*.json','*.safetensors','*.txt','*.model','*.jinja'])" \
    > /dev/null 2>&1 || { echo "download failed: $ID"; continue; }
  HF_HUB_OFFLINE=1 python3 evaluate.py --dataset dataset --models "hf:$ID" --per-cell 1 --pairs 30 --probes 4 \
    --blind --workers 1 --run "$RUN" 2>&1 | grep -E "calls to make|done,|report written|Error|error" || echo "evaluation failed: $ID"
done
echo "== finished $(date -u +%H:%M:%S)"
