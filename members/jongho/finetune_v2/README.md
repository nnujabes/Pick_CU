# finetune_v2 — EXAONE-3.5-7.8B로 같은 과제 파인튜닝 (A.X 비교용)

> finetune_v1(A.X-4.0-Light)과 같은 데이터·같은 규칙으로 원본 모델만 바꿔 학습했다. test는 2026-11-09에 1회 측정했다.
> 비교 결과는 `test_results/test_summary_compare.md`에 있다.

## 목적

문장 → 조건 JSON 변환에서 A.X-4.0-Light와 EXAONE-3.5-7.8B-Instruct 중 어느 모델이 나은지 같은 조건으로 비교한다.

## 폴더 구조

```
finetune_v2/
├─ code/
│  ├─ train_qlora.py, prepare_data.py, dev_pair_baseline.py, bench_train.py  ← finetune_v1 복사 후 EXAONE용으로 수정
│  ├─ check_model.py        ← 학습 전 점검 (대화 형식, 토큰 경계, 층 이름, 4bit 로딩)
│  ├─ eval_best.py          ← best 어댑터로 dev·test 1회 평가
│  └─ query_parser.py       ← 앱용 parse_query (EXAONE용으로 수정, 앱 연결은 확인 안 함)
├─ adapter/best/            ← LoRA 어댑터 (adapter_model.safetensors는 git에 없음, 따로 공유)
├─ data/                    ← train·dev·학습 프롬프트 (hayoung/dev_pair_v3_baseline과 같은 파일)
├─ data_info/               ← 데이터 분할 정보 (finetune_v1과 같은 분할)
├─ results/                 ← 학습 기록 (config, epoch별 val, dev_best, check_model)
├─ test_results/            ← test 1회 측정 요약과 A.X 비교 (문장이 든 ft/는 git 제외)
├─ run_all.sh               ← 서버에서 점검 → 데이터 준비 → smoke → 본 학습을 이어서 실행
├─ requirements.txt, env_info.txt  ← 서버에서 확인한 패키지 버전·환경
└─ MANIFEST.txt, SHA256SUMS.txt    ← 파일 목록·해시
```

## 모델·어댑터

| 항목 | 값 |
|---|---|
| 원본 모델 | `LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct` (revision `553ea250…`, trust_remote_code) |
| 방식 | QLoRA (4bit NF4), r=16, alpha=32, dropout 0.05, lr=2e-4, seed 42 (finetune_v1과 같음) |
| LoRA 대상 층 | `q_proj, k_proj, v_proj, out_proj, c_fc_0, c_fc_1, c_proj` (A.X의 q,k,v,o,gate,up,down에 해당, lm_head 제외) |
| best | epoch 3 (사용자 요청으로 epoch 5 도중 중단) |
| 시스템 프롬프트 sha256 | `06818f0f…b556` (finetune_v1 학습 프롬프트와 같음) |
| 학습 장소 | robot150 서버 RTX 4090, 2026-11-09 |

## 결과

| 평가 | A.X (finetune_v1) | EXAONE (finetune_v2) |
|---|---|---|
| val (best epoch) | 234/270 = 86.7% | 231/270 = 85.6% |
| dev 216 | 186/216 = 86.1% | 182/216 = 84.3% |
| test 240 | 206/240 = 85.8% | 212/240 = 88.3% |

두 모델의 차이는 통계적으로 구분되지 않는다(dev McNemar p=0.56, test p=0.29). 자세한 내용과 같지 않은 조건은 `test_results/test_summary_compare.md`.

### epoch별 val

| epoch | val 완전 일치 | val loss | train loss |
|---|---|---|---|
| 1 | 217/270 = 80.4% | 0.0271 | 0.0533 |
| 2 | 218/270 = 80.7% | 0.0216 | 0.0045 |
| 3 | **231/270 = 85.6%** | 0.0404 | 0.0023 |
| 4 | 208/270 = 77.0% | 0.0489 | 0.0009 |

## finetune_v1에서 바꾼 것

1. `MODEL_ID`, `MODEL_REVISION`, `trust_remote_code=True` (5개 파일)
2. `chat_ids()`: EXAONE은 `[|assistant|]`가 특수 토큰이 아니라 답의 첫 글자 `{`와 토큰이 붙는다(`]{`). 질문과 답을 따로 토큰화해 이어 붙인다. 학습하는 글자(전체 대화에서 질문 부분을 뺀 나머지)는 v1과 같다.
3. `fix_exaone_embeddings()`: EXAONE 모델 코드에 `get_input_embeddings`가 없어 gradient checkpointing과 어댑터 저장이 실패한다. `transformer.wte`를 알려 준다.
4. `TARGET_MODULES`: 층 이름이 달라 명시했다. `all-linear`로 두면 lm_head까지 잡힌다.
5. `prepare_data.py`의 끝 토큰 확인을 `<|im_end|>` 대신 `tok.eos_token`(`[|endofturn|]`)으로 바꿨다(기록용).
6. transformers 5.1.0: EXAONE 모델 코드가 5.20.2에서는 `input_embeds` 오류, 4.57.1에서는 `RopeParameters` 오류가 난다.

`train_qlora.py` 출력의 `baseline_dev_exact 43.5%`는 A.X 값이 코드에 남아 있는 것이다.

## 실행 (서버, `finetune_v2/` 기준)

```
bash run_all.sh                                   # 점검 → 데이터 준비 → smoke → 본 학습
python code/eval_best.py ckpt/run_r16_lr2e-4/best data/dev_pair_v3.csv <test csv> <결과 폴더>
```

test csv는 git에 없다(팀 규칙). 결과 폴더가 이미 있으면 평가를 멈춘다.

## 어댑터 받기

`adapter/best/adapter_model.safetensors`(167,833,632바이트)는 git에 없다. 따로 받아 넣고 해시를 확인한다.

```
sha256  9d65f52a43f16fe3150d6ba54beef6f6198db400b23ebd73df79821f2e6afaa2
```
