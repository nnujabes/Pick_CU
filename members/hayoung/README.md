# hayoung

## 담당 역할

LLM을 담당했습니다. 여러 실험을 거쳐 최종 모델을 선정하고 파인튜닝했으며, 사용자가 입력한 문장을 추천 조건으로 바꾸는 자연어 처리 함수 `parse_query`를 만들었습니다.

- **최종 모델 선정:** 프롬프트 개선과 파인튜닝 결과를 비교한 뒤, `skt/A.X-4.0-Light`를 QLoRA로 파인튜닝한 모델을 서비스 모델로 정했습니다. 프롬프트만 개선했을 때는 dev 정확도가 43.5%였고, 파인튜닝 후에는 86.1%였습니다.
- **파인튜닝:** 원본 모델을 4bit(NF4)로 불러와 LoRA(r=16, alpha=32, lr=2e-4)를 학습했습니다. train 2,550문장으로 학습하고 val 270문장으로 best epoch(1)를 골랐습니다.
- **영양 성분·방향 추출:** 파인튜닝한 모델이 문장에서 영양 성분 2개와 각각의 방향(높음/낮음)을 뽑습니다.
- **예산 추출:** 모델을 쓰지 않고 규칙 코드(`extract_budget`)가 금액을 뽑습니다. 예산 규칙에는 종호 님의 수정안을 반영했습니다.

## 최종 결과

test 240문장의 완전 정확도는 **85.8% (206/240)** 입니다. 같은 조건에서 측정한 원본 모델의 62.5% (150/240)보다 23.3%p 높습니다.

- 완전 정확도는 영양소 2개와 방향이 모두 맞은 문장의 비율이며, 순서는 보지 않습니다.
- 측정은 2026-11-06에 RTX 4060, 4bit 조건으로 1회 진행했습니다.
- 85.8%는 "관계없는 문장" 규칙을 넣기 전의 최종 성적입니다. 규칙을 넣은 현재 프롬프트의 dev 정확도는 85.6% (185/216)입니다.
- test는 12개 상황, 작성자 1명의 데이터라는 한계가 있습니다.

자세한 내용은 `finetune_v1/README.md`의 "최종 test 측정 결과"를 참고해 주세요.

## 이 폴더가 하는 일

| 위치 | 내용 |
| --- | --- |
| `finetune_v1/` | **서비스에서 쓰는 폴더.** `parse_query` 코드, 어댑터 안내, 최종 test 기록 |
| 그 밖의 폴더 | 파인튜닝 전후의 실험 기록(데이터, 코드, 프롬프트, 결과, 로그) |

### 실험 기록

아래 표의 정확도는 실험 단계의 dev 216문장 기준 **완전 정답률**(두 쌍 모두 맞힘, 순서 무관)입니다.

| 순서 | 폴더 | 내용 | dev 완전 정답률 |
| --- | --- | --- | --- |
| 0 | `baseline/` | 11/3 첫 실험 A·B (`eval.jsonl` 40문장, 성분 1개) | B: 37/40 |
| 1 | `dev_baseline/` | 성분 1개+방향, few-shot 9개 (`data/dev.csv`) | 179/216 = 82.9% |
| 2 | `prompt_exp/` | 프롬프트 방식 5가지 비교 (train에서 뗀 val 540문장) | `val_summary.json` |
| 3 | `label_review/` | 라벨 검토용 파일 생성·채점 스크립트 | - |
| 4 | `dev_2nut_baseline/` | **성분 2개로 과제 변경** 후 첫 평가 (`data/dev_2nut.csv`) | **31/216 = 14.4%** |
| 5 | `dev_pair_baseline/` | 팀 확정 짝 규칙표로 라벨 교체 + 규칙 예시 10개 (`data/dev_pair.csv`) | 95/216 = 44.0% |
| 6 | `dev_pair_v2_baseline/` | 데이터 v2 (`data/dev_pair_v2.csv`) | 92/216 = 42.6% |
| 7 | `dev_pair_v3_baseline/` | 데이터 v3: "가볍게·순한" 표현 수정 (`make_v3.py`, `수정내역_v3.csv`) | 94/216 = 43.5% |
| 8 | `ft_ax_v1/` | **QLoRA 파인튜닝** (train_pair_v3, best = epoch 1) | **186/216 = 86.1%** |

- 4~7은 파인튜닝 없이 프롬프트만 쓴 결과(bf16, greedy)이고, 8은 4bit NF4 + LoRA 결과입니다.
- 14.4% → 44.0%의 상승은 데이터 라벨 정비 및 **라벨을 짝 규칙표로 통일하고 프롬프트 규칙 예시를 바꾼 효과**입니다.
- 그 밖에 `wsl_LLM_CU_project/`는 로컬 WSL 작업 폴더 스냅샷(크롤러, 추천 앱, GGUF 실험)이고, `docs/`에는 실험 지시서 PDF와 인수인계 문서 `HANDOFF.md`가 있습니다.

### 파인튜닝 요약 (`ft_ax_v1/`)

- 데이터: `data/train_pair_v3.csv` 94상황 2,820문장 → train 85상황 2,550문장 / val 9상황 270문장 (상황 단위, seed 42, 규칙 예시 상황은 val에서 제외). dev는 학습·선택에 쓰지 않고 마지막에 1회만 평가했습니다. 이 단계에서 test는 쓰지 않았습니다.
- 설정: 4bit NF4(double quant, bf16 연산), LoRA r16 / alpha 32 / dropout 0.05 / 7개 linear 전부, lr 2e-4 cosine(warmup 3%), 유효 배치 16, 최대 10 epoch, early stopping patience 3 (기준: val 완전 정답률), loss는 답변 토큰에만 적용했습니다.
- 결과: epoch 4에서 조기 종료, best = epoch 1 (val 234/270 = 86.7%). dev 186/216 = 86.1%, 첫째를 맞히면 둘째도 100% 맞혔고, 형식 오류는 0건입니다.
- 약점: S2008(정답 당류↑ 열량↑)을 탄수화물↑로 답하는 경우가 많습니다 (4/17).
- 소요: RTX 4090 1장, 56분.

## 실행 방법

### 서비스에서 쓰기

저장소 최상위 폴더에서 실행합니다. 준비할 것과 어댑터 받는 방법은 `finetune_v1/README.md`에 있습니다.

```python
import sys
sys.path.insert(0, "members/hayoung/finetune_v1/code")
from query_parser import parse_query

parse_query("5천원 이하로 운동 후에 먹을 거")
# {"budget": 5000, "nutrients": {"단백질": "high", "지방": "low"}}
```

### 실험 재현

서버 166(RTX 4090) conda env `llm-ft`에서 확인했습니다. 아래 명령은 이 폴더(`members/hayoung/`)에서 실행합니다.

```bash
# 환경 (Python 3.10, CUDA 12.4)
pip install -r requirements_llm-ft.txt

# 전체 재현 + 저장된 결과와 비교 (약 30분, GPU 24GB). 학습 본 실행은 하지 않는다.
bash reproduce_all.sh repro_out
cat repro_out/compare_result.txt

# 개별 실행 예
python dev_pair_v3_baseline/dev_pair_baseline.py run data/dev_pair_v3.csv out/v3        # 프롬프트만 (out 폴더는 미리 만들 것)
python ft_ax_v1/code/eval_adapter.py ft_ax_v1/ckpt/run_r16_lr2e-4/best data/dev_pair_v3.csv out/ft_dev   # 파인튜닝 모델 평가

# 파인튜닝 다시 하기 (약 1시간)
python ft_ax_v1/code/prepare_data.py data/train_pair_v3.csv dev_pair_v3_baseline/prompt.txt ft_ax_v1/code/dev_pair_baseline.py ft_ax_v1/ft_data
python ft_ax_v1/code/train_qlora.py ft_ax_v1 data/train_pair_v3.csv data/dev_pair_v3.csv --epochs 10 --patience 3 --lr 2e-4 --r 16 --run run_r16_lr2e-4
```

## 핵심 함수

### 서비스용 (`finetune_v1/code/query_parser.py`)

| 이름 | 입력 | 출력 | 예시 |
| --- | --- | --- | --- |
| `parse_query(text)` | 입력 문장 | 조건 딕셔너리, 실패하면 `None` | `{"budget": 5000, "nutrients": {"단백질": "high", "지방": "low"}}` |
| `parse_query_with_reason(text)` | 입력 문장 | `(결과, 실패 이유)` | `(None, "no_condition")` |

성분 이름은 열량·단백질·나트륨·탄수화물·당류·지방이고, 방향은 `high`, `low`입니다.
예산은 모델이 아니라 규칙 코드가 뽑습니다.

### 실험용

| 이름 | 입력 | 출력 | 예시 |
| --- | --- | --- | --- |
| `dev_pair_baseline.build_messages(text)` | 입력 문장 | 채팅 메시지(system 프롬프트 + 문장) | `build_messages("운동 끝나고 뭐 먹지")` |
| `dev_pair_baseline.parse_output(text)` | 모델 출력 문자열 | `(items, parse_ok, schema_ok)` | `[("protein","high"),("fat","low")]` |
| `dev_pair_baseline.score(gold1, gold2, items)` | 정답 두 쌍, 예측 | 완전 정답·쌍 정확도 등 | 순서 무관 집합 비교 |
| `train_qlora.generate_eval(model, tok, rows, ...)` | 모델, CSV 행 | 문장별 예측과 채점 | greedy, 128토큰 |
| `eval_adapter.main(adapter, csv, out)` | 어댑터 폴더, CSV | `rows.csv`, `wrong.csv`, `summary.json` | 위 실행 방법 참고 |

실험용 모델의 출력 형식: `{"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "fat", "direction": "low"}]}`
성분은 `calories, protein, sodium, carbs, sugar, fat` 중 하나, 방향은 `high, low`입니다.

## 필요한 라이브러리

- 서비스용: `finetune_v1/requirements.txt` (torch는 PC의 CUDA 버전에 맞게 먼저 설치)
- 실험 재현용: `requirements_llm-ft.txt` (서버 env `llm-ft`의 `pip freeze`). 핵심: torch 2.6.0+cu124, transformers 5.20.2, peft 0.21.2, bitsandbytes 0.50.2, accelerate 1.15.0. `label_review/`는 openpyxl이 필요합니다.

## 통합 위치

`members/jongho/fastapi/service.py`가 `finetune_v1/code/query_parser.py`를 불러와 사용합니다. 어댑터 기본 위치는 `finetune_v1/adapter/best/`입니다.

## 주의

- 저장소 `.gitignore` 때문에 `data/`, `*.log`, `*.safetensors`(어댑터 가중치 155MB)는 git에 올라가지 않습니다. 팀원에게는 따로 전달해야 합니다.
- `label_review/blind_key_DO_NOT_SHARE.csv`는 일부러 넣지 않았습니다.
- `rows.csv`, `wrong.csv`, `make_v3.py`, `data/`에는 dev 문장 원문이 들어 있습니다.
- `finetune_v1/test_results/`의 `test_data/`, `rows.csv`, `wrong.csv`에는 test 문장 원문이 들어 있습니다. 측정이 끝난 시험지이므로 학습·튜닝·프롬프트 개선에 사용하지 않습니다.
