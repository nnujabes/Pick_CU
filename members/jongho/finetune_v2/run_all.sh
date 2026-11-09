#!/bin/bash
# 서버에서 한 번에 실행: 점검 -> 데이터 준비 -> smoke -> 본 학습(+dev 평가). 실패하면 그 단계에서 멈춘다.
# 실행 위치: ~/jongho_ft_v2 (finetune_v2 폴더 내용을 그대로 올린 곳)
set -eo pipefail
cd ~/jongho_ft_v2
PY=~/miniforge3/envs/jongho-exaone/bin/python
mkdir -p logs results
step() { echo "[$(date '+%F %T')] $1" | tee -a logs/progress.log; }

step "1/4 check_model 시작"
(cd code && $PY check_model.py ../results/check_model.json) 2>&1 | tee logs/check_model.log
step "1/4 check_model 끝"

step "2/4 prepare_data 시작"
$PY code/prepare_data.py data/train_pair_v3.csv data/prompt.txt code/dev_pair_baseline.py ft_data 2>&1 | tee logs/prepare_data.log
step "2/4 prepare_data 끝"

step "3/4 smoke 시작"
$PY code/train_qlora.py . data/train_pair_v3.csv data/dev_pair_v3.csv --smoke 1 --run smoke 2>&1 | tee logs/smoke.log
step "3/4 smoke 끝"

step "4/4 본 학습 시작 (v1과 같은 규칙: 최대 10 epoch, patience 3, r16, lr 2e-4)"
$PY code/train_qlora.py . data/train_pair_v3.csv data/dev_pair_v3.csv --run run_r16_lr2e-4 2>&1 | tee logs/train.log
step "4/4 본 학습 끝"
step "ALL_DONE"
