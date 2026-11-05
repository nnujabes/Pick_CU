# hayoung

## 담당 역할

LLM 담당. 사용자의 자연어 요청 문장에서 **영양 성분 2개와 각각의 방향(높음/낮음)** 을 뽑는 모델을 만든다.
모델은 `skt/A.X-4.0-Light` (rev `ba21c20ea1b31ded1ec3e2fb432335077dc4be98`)이고, QLoRA로 파인튜닝했다.

## 이 폴더가 하는 일

실험 기록 전체(데이터, 코드, 프롬프트, 결과, 로그)와 파인튜닝 어댑터를 보관한다. 모든 정확도는 dev 216문장 기준 **완전 정답률**(두 쌍 모두 맞힘, 순서 무관)이다.

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

- 4~7은 파인튜닝 없이 프롬프트만 쓴 결과(bf16, greedy)이고, 8은 4bit NF4 + LoRA 결과다.
- 14.4% → 44.0%의 상승은 데이터 보강이 아니라 **라벨을 짝 규칙표로 통일하고 프롬프트 규칙 예시를 바꾼 효과**다.
- 그 밖에 `wsl_LLM_CU_project/`는 로컬 WSL 작업 폴더 스냅샷(크롤러, 추천 앱, GGUF 실험)이고, `docs/`에는 실험 지시서 PDF와 인수인계 문서 `HANDOFF.md`가 있다.

### 파인튜닝 요약 (`ft_ax_v1/`)

- 데이터: `data/train_pair_v3.csv` 94상황 2,820문장 → train 85상황 2,550문장 / val 9상황 270문장 (상황 단위, seed 42, 규칙 예시 상황은 val에서 제외). dev는 학습·선택에 쓰지 않고 마지막에 1회만 평가. test는 쓰지 않음.
- 설정: 4bit NF4(double quant, bf16 연산), LoRA r16 / alpha 32 / dropout 0.05 / 7개 linear 전부, lr 2e-4 cosine(warmup 3%), 유효 배치 16, 최대 10 epoch, early stopping patience 3 (기준: val 완전 정답률), loss는 답변 토큰에만.
- 결과: epoch 4에서 조기 종료, best = epoch 1 (val 234/270 = 86.7%). dev 186/216 = 86.1%, 첫째를 맞히면 둘째도 100% 맞힘, 형식 오류 0건.
- 약점: S2008(정답 당류↑ 열량↑)을 탄수화물↑로 답하는 경우가 많음 (4/17).
- 소요: RTX 4090 1장, 56분.

## 실행 방법

서버 166(RTX 4090) conda env `llm-ft`에서 확인했다. 모든 명령은 이 폴더(`members/hayoung/`)에서 실행한다.

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

| 이름 | 입력 | 출력 | 예시 |
| --- | --- | --- | --- |
| `dev_pair_baseline.build_messages(text)` | 입력 문장 | 채팅 메시지(system 프롬프트 + 문장) | `build_messages("운동 끝나고 뭐 먹지")` |
| `dev_pair_baseline.parse_output(text)` | 모델 출력 문자열 | `(items, parse_ok, schema_ok)` | `[("protein","high"),("fat","low")]` |
| `dev_pair_baseline.score(gold1, gold2, items)` | 정답 두 쌍, 예측 | 완전 정답·쌍 정확도 등 | 순서 무관 집합 비교 |
| `train_qlora.generate_eval(model, tok, rows, ...)` | 모델, CSV 행 | 문장별 예측과 채점 | greedy, 128토큰 |
| `eval_adapter.main(adapter, csv, out)` | 어댑터 폴더, CSV | `rows.csv`, `wrong.csv`, `summary.json` | 위 실행 방법 참고 |

모델 출력 형식: `{"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "fat", "direction": "low"}]}`
성분은 `calories, protein, sodium, carbs, sugar, fat` 중 하나, 방향은 `high, low`.

## 필요한 라이브러리

`requirements_llm-ft.txt` (서버 env `llm-ft`의 `pip freeze`). 핵심: torch 2.6.0+cu124, transformers 5.20.2, peft 0.21.2, bitsandbytes 0.50.2, accelerate 1.15.0. `label_review/`는 openpyxl이 필요하다.

## 통합 때 옮길 위치

미정. 앱에서는 `build_messages` → 생성 → `parse_output` 흐름과 best 어댑터(`ft_ax_v1/ckpt/run_r16_lr2e-4/best/`)를 쓰면 된다.

## 주의

- 저장소 `.gitignore` 때문에 `data/`, `*.log`, `*.safetensors`(어댑터 가중치 155MB)는 git에 올라가지 않는다. 팀원에게는 따로 전달해야 한다.
- `label_review/blind_key_DO_NOT_SHARE.csv`는 일부러 넣지 않았다.
- `rows.csv`, `wrong.csv`, `make_v3.py`, `data/`에는 dev 문장 원문이 들어 있다.
