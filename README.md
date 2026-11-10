# Pick_CU — 편의점 큐레이터

(A)I-Net 팀의 LLM 수업 프로젝트입니다. 편의점(CU) 제품의 영양 성분 라벨을 하나하나 보지 않아도, 원하는 조건을 문장으로 말하면 상품 조합을 추천해 줍니다.

예: "운동 끝나고 5천원으로 먹을 거 추천해줘" + 카테고리 간편식사, 음료 → 단백질 높고 지방 낮은 조합 Top 5

## 추천 흐름

| 단계 | 하는 일 | 코드 |
| --- | --- | --- |
| 1. 자연어 전처리 | A.X-4.0-Light(LoRA 파인튜닝)가 영양 조건 2개를 뽑고, 예산은 규칙으로 뽑는다 | `backend/pickcu/query_parser.py`, `backend/pickcu/nlu.py` |
| 2. 가격 필터 | 예산이 있으면 단품 가격 상한을 검색 조건에 넣는다 | `backend/pickcu/product_search.py` |
| 3. DB 조회 | 고른 카테고리마다 SQLite에서 후보 상품을 꺼낸다 | `backend/pickcu/product_search.py` |
| 4. Top 5 필터 | 카테고리별 1개씩 조합하고 영양 0.7 + 가격 0.3 점수로 순위를 매긴다 | `backend/pickcu/filter_engine.py` |
| 5. 화면 표시 | 추천 카드, 별점, 장바구니 | `frontend/` |

LLM은 1단계에서만 씁니다. 웹 API(`backend/api/service.py`)는 4단계 순위를 정하기 전에 리뷰 별점 점수(10 × R)를 더하며, 리뷰가 없으면 엔진 결과와 같습니다.

## 폴더 구조

```
backend/
  pickcu/      추천 로직 (웹 없이도 쓰는 패키지)
               filter_engine.py, product_search.py, query_parser.py, nlu.py
  api/         FastAPI 서버 (main.py, service.py, review_store.py) — API 명세는 api/README.md
  data/        cu_products.db(상품 2,154개), 카테고리별 products.csv, exclude_items.csv
               reviews.db는 실행할 때 생기며 커밋하지 않음
  models/      A.X LoRA 어댑터 (git 제외)
  scripts/     build_cu_products_db.py(상품 DB 생성), build_mocks.py(mock 응답 생성)
  tests/       엔진, 검색, API 시험
  requirements.txt
frontend/      웹 화면 (React + Vite + Tailwind)
docs/          interface.md — 팀원끼리 주고받는 함수와 데이터 형식 약속
members/       팀원별 작업 폴더 (실험, 학습, 이전 버전)
```

## 실행

필요한 것: Python(CUDA용 torch 포함), Node.js, NVIDIA GPU 메모리 약 5GB 이상. Windows는 bitsandbytes 설치가 어려워 WSL·Linux를 권합니다.

1. Python 패키지

   ```bash
   pip install -r backend/requirements.txt   # torch는 PC의 CUDA 버전에 맞게 따로 설치
   ```

2. A.X 어댑터: 어댑터 파일은 용량 때문에 git에 없고 Hugging Face에 공개로 올려 두었습니다(https://huggingface.co/nnujabes/pickcu-ax-4.0-light-lora, 약 162MB). 로그인 없이 받을 수 있습니다.

   ```bash
   pip install -U huggingface_hub
   # README.md는 받지 않도록 파일 두 개만 지정
   hf download nnujabes/pickcu-ax-4.0-light-lora adapter_model.safetensors adapter_config.json \
     --local-dir backend/models/adapter/best
   sha256sum backend/models/adapter/best/adapter_model.safetensors
   # f95d9f5e429f0f16c854c769253ee0dd4df075f91b5ea3cc29fd56b7b157cc8b
   ```

   다른 곳에 두었으면 환경변수 `QUERY_PARSER_ADAPTER`로 경로를 지정합니다. 첫 실행 때 `skt/A.X-4.0-Light` 원본(약 15GB)을 받습니다. 양자화 GGUF 모델(web3용)은 `members/hyeokjun/huggingface/README.md`를 참고합니다.

3. 화면과 API를 함께 실행

   ```bash
   cd frontend
   npm install
   npm start          # API(http://127.0.0.1:8000)와 화면(http://localhost:5173)
   ```

   `npm start`는 현재 셸의 `python`으로 API를 띄우므로, 1번 패키지를 설치한 Python 환경을 먼저 활성화합니다.

- API만 실행: `cd backend && python -m uvicorn api.main:app --port 8000` (API 문서 http://127.0.0.1:8000/docs)
- GPU 없이 실행: `PICKCU_PARSER=rule`을 주면 규칙 파서(`nlu.py`)로 동작합니다. A.X를 불러오지 못할 때도 규칙 파서로 동작합니다.

## 시험

```bash
cd backend
python tests/test_filter_engine.py
python tests/test_product_search.py
python -m unittest discover -s tests -p "test_api.py"
```

API 시험은 규칙 파서 기준이라 GPU 없이 돕니다. A.X 시험은 모델을 불러오지 못하면 건너뜁니다.

## 상품 DB 다시 만들기

`backend/data/csv/`의 카테고리별 `products.csv`를 읽어 `cu_products.db`를 새로 만듭니다. `exclude_items.csv`에 적은 상품(소스·양념·조미료, 식재료)은 DB에 남기되 추천 검색에서 뺍니다.

```bash
python backend/scripts/build_cu_products_db.py
```

## 통합 코드의 원본

| 통합 위치 | 원본 |
| --- | --- |
| `backend/api/`, `backend/pickcu/nlu.py` | `members/jongho/fastapi/` |
| `backend/pickcu/query_parser.py` | `members/hayoung/finetune_v1/code/query_parser.py` |
| `backend/pickcu/filter_engine.py`, `product_search.py`, `backend/data/` | knlee |
| `frontend/` | `members/hyeokjun/curator_web2/` |

## 팀원별 작업

| 팀원 | 담당 | 주요 결과물 | 서비스에 쓰인 곳 |
| --- | --- | --- | --- |
| hayoung | LLM 선정·파인튜닝, 자연어 전처리 | A.X-4.0-Light QLoRA 모델, `parse_query` | `backend/pickcu/query_parser.py` |
| jongho | API 서버, 예산 규칙, 모델 비교 | FastAPI 서버, 규칙 파서, `budget_filter`, EXAONE 비교 | `backend/api/`, `backend/pickcu/nlu.py` |
| hyeokjun | 웹 화면, A.X 기준선 평가 | 웹 화면 3종(curator_web, web2, web3) | `frontend/` (curator_web2) |
| knlee | 데이터 수집·DB, 추천 엔진, 통합 | 상품 DB 2,154개, 검색 함수, Top 5 필터 엔진 | `backend/pickcu/`(엔진·검색), `backend/data/` |

### hayoung — 문장 해석 모델 (`members/hayoung/`)

- 프롬프트만 개선한 방식과 파인튜닝을 비교했습니다. 프롬프트만 쓴 dev 정확도는 최고 43.5%, 파인튜닝 후는 86.1%여서 파인튜닝 모델을 서비스 모델로 정했습니다.
- 실험 과정
  - 영양 성분 1개 추출에서 2개 추출로 과제를 바꿨습니다(dev 14.4%).
  - 짝 규칙표로 라벨을 통일하자 44.0%가 되었습니다.
  - 데이터 v2, v3를 만들었습니다.
  - 마지막으로 QLoRA 파인튜닝을 했습니다(dev 86.1%).
- 파인튜닝 설정
  - 4bit NF4, LoRA r16·alpha32, lr 2e-4
  - train 2,550문장, best epoch 1
- 최종 test 240문장 완전 정확도는 **85.8%**입니다. 원본 모델은 62.5%였습니다.
- `parse_query(text)`
  - 영양 성분 2개와 방향(high/low)은 모델이, 예산은 규칙 코드가 뽑습니다.
  - 인사나 잡담처럼 관계없는 문장이면 `None`을 돌려줍니다.
  - `parse_query_with_reason`은 실패 이유도 함께 돌려줍니다.

### jongho — API 서버와 예산 규칙 (`members/jongho/`)

- `fastapi/`: 화면이 호출하는 API 서버
  - 추천(`/recommend`), 상품 목록(`/products`), 리뷰(`/reviews`)
  - A.X 해석을 연결했고, A.X를 쓸 수 없으면 규칙 파서(`nlu.py`)로 동작합니다.
  - 영양소를 찾지 못하면 `no_nutrient` 상태와 이유를 돌려주어 화면이 다시 묻게 합니다.
  - 예산 안에 결과가 없으면 예산을 10% 넓혀 다시 찾습니다.
  - 리뷰 별점을 추천 순위에 반영합니다(엔진 총점 + 10 × R).
  - API 명세는 `backend/api/README.md`에 있습니다.
- `budget_lab/`: 예산 함수 수정안 `budget_filter`
  - 이미 쓴 금액("어제 3만원 썼는데")은 예산에서 뺍니다.
  - 10만원을 넘는 금액은 예산이 없는 것으로 봅니다.
  - "0.5원" 같은 1원 미만 금액은 0원으로 읽고, 서버가 1000원 이상으로 다시 입력하도록 안내합니다.
  - hayoung의 `parse_query`에는 아직 반영되지 않았습니다(반영 요청서 `budget_lab/README_budget_filter_반영요청.md`). 서비스는 지금 이전 함수 `extract_budget`을 씁니다.
- `eval/`: 파인튜닝 어댑터 평가 스크립트
- `finetune_v2/`: 같은 데이터로 EXAONE-3.5-7.8B를 파인튜닝해 A.X와 비교했습니다.
  - test는 EXAONE 88.3%, A.X 85.8%입니다.
  - 두 모델의 차이는 통계적으로 구분되지 않아(McNemar p=0.29) 서비스는 A.X를 유지했습니다.

### hyeokjun — 웹 화면 (`members/hyeokjun/`)

- A.X 4.0 Light 기준선을 평가했습니다(Ollama Q5_K_M).
  - 직접 말한 영양소는 100%를 맞혔습니다.
  - 상황 표현(strict 13%), 제외 표현(53%), 전문용어(40%)는 약했습니다.
- `curator_web/`: 3D 편의점 모형이 있는 첫 웹 화면입니다. 실제 상품 DB와 엔진 결과를 쓰고 장바구니와 리뷰가 있습니다.
- `curator_web2/`: 대시보드형 화면으로, **서비스 화면(`frontend/`)의 원본**입니다.
  - 네온 간판과 다크·화이트 모드
  - 카테고리 세부 분류, 전체 상품 화면
  - 장바구니, 별점 랭킹, 휴대폰 화면
- `curator_web3/`: 양자화한 A.X(GGUF, Ollama)로 화면, API, 모델을 한 번에 실행하는 버전입니다.

### knlee — 데이터와 추천 엔진 (`members/knlee/`, `backend/`)

- CU 상품 정보와 영양성분표 이미지를 수집했습니다(`crawl_cu.py`).
- Qwen2.5-VL-7B로 이미지에서 영양소 6개를 추출하고 검증했습니다(`vlm_nutrition_parser.py`).
  - 이미지 3,873건 중 2,154개 상품을 DB에 넣었습니다.
- 상품 DB(`cu_products.db`)를 만들었습니다.
  - 소스·양념·조미료와 식재료 24개는 DB에 남기되 추천 검색에서 뺐습니다.
- `product_search.py`: 카테고리별 후보 검색. 예산이 있으면 단품 가격 상한을 겁니다.
- `filter_engine.py`: 카테고리별 1개씩 조합해 Top 5를 고릅니다.
  - 점수는 영양 0.7 + 가격 0.3입니다.
  - 카테고리가 3개면 후보를 50+30개로 줄입니다.
  - 중복 상품과 맛만 다른 상품은 제거합니다.
  - 시험은 엔진 37개, 검색 23개입니다.
- 팀원 코드를 서비스 폴더 `backend/`, `frontend/`로 통합했습니다(PR #42~#45).
