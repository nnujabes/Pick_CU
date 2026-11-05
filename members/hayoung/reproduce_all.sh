#!/usr/bin/env bash
# members/hayoung 안의 파일만으로 주요 실험을 다시 돌리고, 저장된 결과와 비교한다.
# 필요: CUDA GPU(24GB 권장), requirements_llm-ft.txt 환경, skt/A.X-4.0-Light (rev ba21c20e…) 다운로드 가능
# usage: bash reproduce_all.sh [출력폴더(기본 repro_out)]
# 학습 본 실행은 하지 않는다 (train_qlora.py는 --smoke 1로 흐름만 점검). test 데이터는 쓰지 않는다.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-repro_out}"
PY="${PYTHON:-python}"
mkdir -p "$OUT"
echo "[$(date +%T)] start, python=$($PY -c 'import sys;print(sys.executable)')"

# 1) 파인튜닝 전 기준점 (bf16, greedy)
mkdir -p "$OUT/dev_baseline"
$PY -B dev_baseline/dev_baseline.py data/train.csv data/dev.csv "$OUT/dev_baseline/dev_baseline"
mkdir -p "$OUT/dev_2nut_baseline" && $PY -B dev_2nut_baseline/dev_2nut_baseline.py run data/dev_2nut.csv "$OUT/dev_2nut_baseline"
mkdir -p "$OUT/dev_pair_baseline" && $PY -B dev_pair_baseline/dev_pair_baseline.py run data/dev_pair.csv "$OUT/dev_pair_baseline"
mkdir -p "$OUT/dev_pair_v2_baseline" && $PY -B dev_pair_v2_baseline/dev_pair_baseline.py run data/dev_pair_v2.csv "$OUT/dev_pair_v2_baseline"
mkdir -p "$OUT/dev_pair_v3_baseline" && $PY -B dev_pair_v3_baseline/dev_pair_baseline.py run data/dev_pair_v3.csv "$OUT/dev_pair_v3_baseline"

# 2) 파인튜닝 데이터 생성 (train_pair_v3 → train/val jsonl)
$PY -B ft_ax_v1/code/prepare_data.py data/train_pair_v3.csv dev_pair_v3_baseline/prompt.txt \
    ft_ax_v1/code/dev_pair_baseline.py "$OUT/ft_data"

# 3) 저장된 best 어댑터로 dev 평가 (4bit + LoRA)
$PY -B ft_ax_v1/code/eval_adapter.py ft_ax_v1/ckpt/run_r16_lr2e-4/best data/dev_pair_v3.csv "$OUT/ft_dev_best"

# 4) 학습 코드 흐름 점검 (epoch당 2 step)
mkdir -p "$OUT/ft_smoke"
cp "$OUT/ft_data/"*.jsonl "$OUT/ft_data/data_info.json" "$OUT/ft_smoke/" 2>/dev/null || true
mkdir -p "$OUT/ft_smoke/ft_data" && mv "$OUT/ft_smoke/"*.jsonl "$OUT/ft_smoke/data_info.json" "$OUT/ft_smoke/ft_data/"
$PY -B ft_ax_v1/code/train_qlora.py "$OUT/ft_smoke" data/train_pair_v3.csv data/dev_pair_v3.csv \
    --epochs 2 --patience 3 --lr 2e-4 --r 16 --run smoke_test --smoke 1

# 5) 저장된 결과와 비교
$PY -B compare_repro.py "$OUT"
echo "[$(date +%T)] all done"
