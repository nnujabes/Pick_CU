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

2. A.X 어댑터: `adapter_model.safetensors`는 git에 없어서 따로 받아 `backend/models/adapter/best/`에 넣습니다. 다른 곳에 두었으면 환경변수 `QUERY_PARSER_ADAPTER`로 경로를 지정합니다. 첫 실행 때 `skt/A.X-4.0-Light` 원본(약 15GB)을 받습니다.

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
