# finetune_v1 — 문장 → 조건 JSON 변환 (파인튜닝 1차)

> **1차 잠정 모델이며 test는 아직 측정하지 않았습니다.**

## 목적

사용자 문장을 DB 조회용 조건 JSON으로 바꾸는 `parse_query()`와, 이를 위해 파인튜닝한 LoRA 어댑터를 공유합니다.
팀원 각자의 PC에서 파인튜닝 모델을 돌려볼 수 있게 하는 것이 목적이고, 학습 코드와 결과는 기록용으로 함께 둡니다.

## 폴더 구조

```
finetune_v1/
├─ code/
│  ├─ query_parser.py        ← 팀원이 쓰는 함수 (parse_query)
│  ├─ check_query_parser.py  ← 확인 테스트 (기록용)
│  └─ train_qlora.py, prepare_data.py, bench_train.py, dev_pair_baseline.py  ← 실험 기록용
├─ adapter/best/             ← LoRA 어댑터 (adapter_model.safetensors는 git에 없음, 따로 공유)
├─ results/                  ← 학습·평가·확인 테스트 결과
├─ baseline_results/         ← 파인튜닝 전 기준 성능
├─ data_info/                ← 데이터 분할·수정 내역 (데이터 자체는 ../dev_pair_v3_baseline/에 있음)
├─ requirements.txt, env_info.txt  ← 서버에서 확인한 패키지 버전·환경
└─ MANIFEST.txt, SHA256SUMS.txt    ← 묶음 파일 목록·해시 (서버 원본 기준)
```

## 모델·어댑터

| 항목 | 값 |
|---|---|
| 원본 모델 | `skt/A.X-4.0-Light` (revision `ba21c20e…`) |
| 방식 | QLoRA (4bit NF4), r=16, alpha=32, lr=2e-4 |
| best | epoch 1 (4 epoch에서 조기 종료) |
| 시스템 프롬프트 sha256 | `06818f0f…b556` (불러올 때 자동 확인) |

**원본 모델 지정 방식**: `query_parser.py`는 `adapter_config.json`의 `base_model_name_or_path`를 읽지 않고, 코드 안의
`MODEL_ID = "skt/A.X-4.0-Light"`와 `MODEL_REVISION`으로 허깅페이스에서 직접 불러옵니다(값은 adapter_config와 같음).
따로 로컬 경로를 지정하는 설정은 없으며, 처음 실행할 때 허깅페이스 캐시로 내려받습니다.

## 결과

| 평가 | 정확도 (영양소 2개·방향 모두 일치) |
|---|---|
| val (best epoch) | 86.7% (234/270) |
| dev | 43.5% (94/216) → **86.1%** (186/216) |

- dev 조건: 파인튜닝 전은 bf16 + 프롬프트만, 후는 4bit + LoRA.
- **test는 아직 측정하지 않았습니다.**

## 사용법

```python
import sys
sys.path.insert(0, "members/hayoung/finetune_v1/code")
from query_parser import parse_query

parse_query("5천원 이하로 운동 후에 먹을 거")
# {"budget": 5000, "nutrients": {"단백질": "high", "지방": "low"}}
parse_query("야식으로 먹을 건데 2만원대로 짜지 않은 거")
# {"budget": 20000, "nutrients": {"나트륨": "low", "지방": "low"}}
parse_query("요즘 혈당이 걱정돼요")
# {"budget": null, "nutrients": {"당류": "low", "열량": "low"}}   ← 파이썬에서는 None
```

(위 결과는 서버 GPU에서 3번 반복해 같게 나온 값입니다.)

- 반환 형식: `{"budget": 정수 또는 null, "nutrients": {"단백질": "high", "지방": "low"}}`
  - 성분 이름: 열량·단백질·나트륨·탄수화물·당류·지방, 방향: `high`/`low`, 항상 2개
  - 예산은 모델이 아니라 규칙 코드(`extract_budget`)가 뽑습니다.
- **실패하면 `None`** (빈 입력, 300자 초과, 모델 응답 형식 오류, 실행 오류). 이유는 `logging` 경고로 남습니다.
- 어댑터 경로: 기본은 `finetune_v1/adapter/best`. 다른 곳에 두었으면 환경변수로 바꿉니다.
  ```
  set QUERY_PARSER_ADAPTER=D:\models\adapter_best      (Windows cmd)
  export QUERY_PARSER_ADAPTER=/path/to/adapter_best    (Linux/macOS)
  ```
- CLI: `code` 폴더에서 `python -m query_parser "5천원 이하로 운동 후에 먹을 거"`
- 첫 호출 때 모델을 한 번 불러 캐시하고, 이후 호출은 문장당 약 0.8초(RTX 4090 기준)입니다.

## 필요한 것

- NVIDIA GPU (4bit 기준 VRAM 약 5GB 이상, 서버 측정 최대 4.9GiB). CUDA GPU가 없으면 불러오기에서 오류가 납니다.
- 원본 모델 `skt/A.X-4.0-Light` 다운로드 (약 15GB, 허깅페이스. 첫 실행 때 자동으로 받음)
- 패키지 설치:
  1. torch는 PC의 CUDA 버전에 맞게 먼저 따로 설치 (https://pytorch.org 의 안내 명령 사용)
  2. 나머지: `pip install -r members/hayoung/finetune_v1/requirements.txt`
- **한계**: 버전은 서버(Ubuntu, Python 3.10, CUDA 12.4)에서만 확인했습니다(`env_info.txt`). Windows에서는 `bitsandbytes` 설치가 어려울 수 있습니다.

## 어댑터 파일 받기

어댑터 본체(`adapter/best/adapter_model.safetensors`, 161,533,192바이트)는 저장소가 GitHub 무료 요금제라 git에 올리지 않고 팀원끼리 따로 공유합니다(`members/hayoung/.gitignore`).
받은 파일을 `adapter/best/`에 넣고 아래 해시가 맞는지 확인하세요.

```
sha256 f95d9f5e429f0f16c854c769253ee0dd4df075f91b5ea3cc29fd56b7b157cc8b
```

## 한계

- 영양소와 무관한 입력(예: 인사)에도 성분 2개가 나옵니다. 무관한 문장인지는 판단하지 않습니다.
- 모호한 예산 표현("몇 천원", "만원 넘게", "N원짜리" 등)은 못 뽑거나 의도와 다르게 뽑을 수 있습니다. 금액이 여럿이면 먼저 나온 금액을 씁니다.
- 300자를 넘는 입력은 모델을 부르지 않고 `None`을 돌려줍니다.

## 기록용 코드 안내

`train_qlora.py` 등은 서버 경로 기준의 실험 기록용이며 그대로는 재현되지 않을 수 있습니다.
`results/`의 json에 남은 서버 경로(`/home/dgu/...`)도 기록 그대로 두었습니다(저장소가 비공개라 바꾸지 않음).
저장소 복사본에서 바꾼 것은 `code/query_parser.py`의 `DEFAULT_ADAPTER` 한 줄뿐입니다(`ckpt/run_r16_lr2e-4/best` → `adapter/best`).
그래서 `SHA256SUMS.txt`의 `query_parser.py` 해시는 서버 원본 기준이라 이 복사본과 다릅니다.
