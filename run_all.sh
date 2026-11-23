#!/usr/bin/env bash
# Reproduce everything from scratch with one command.
#   ./run_all.sh            full benchmark (≈310 scenes, ~25 min on 4 cores)
#   ./run_all.sh --quick    small version for a quick look (~2 min)
# Real model runs are separate (they need API keys):
#   python3 evaluate.py --dataset dataset --models claude:claude-opus-5-5 --per-cell 3 --blind --run frontier
#   python3 staircase.py --dataset dataset --models claude:claude-opus-5-5 --trials 16 --run frontier_eye
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "--quick" ]]; then
  BUILD=(--per-level 3 --real-per-location 0)
else
  BUILD=(--per-level 50 --real-per-location 15)
fi

echo "== 1/7 tests";                 python3 -m pytest -q
echo "== 2/7 build dataset";         rm -rf dataset && python3 build_dataset.py "${BUILD[@]}" --out dataset --workers "${WORKERS:-4}" > /dev/null
echo "== 3/7 offline baselines";     rm -rf results/offline_baselines
python3 evaluate.py --dataset dataset --models mock:oracle mock:random mock:stubborn --blind --run offline_baselines
echo "== 4/7 adaptive eye exam";     python3 staircase.py --dataset dataset --models mock:oracle mock:random --trials 16 --run eye_offline > /dev/null
echo "== 5/7 validation report";     python3 validation_report.py
echo "== 6/7 independent verification"; python3 verify_results.py --regen 6 > /dev/null
echo "== 7/7 demo + human test pages"
python3 build_demo.py --dataset dataset --run results/offline_baselines --per-skill 4 --pairs 9 --out demo
python3 human_eval.py build --dataset dataset --per-skill 3 --out human_eval
echo "Done. See docs/VALIDATION_REPORT.md, docs/VERIFICATION.md, results/offline_baselines/REPORT.md, demo/index.html"
