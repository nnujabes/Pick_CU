# Pick CU 웹 데모

`backend/data/cu_products.db`의 실제 상품 2,154개와 팀 필터 엔진(`backend/pickcu/`)을 연결한 웹 화면입니다. 팀 코드와 DB는 읽기만 합니다.

API 서버는 `members/jongho/fastapi/`에 있습니다. 이 폴더는 프론트와 API 형식(`api_contract.json`)만 담고 있어서, 화면을 쓰려면 그 서버 코드가 함께 있어야 합니다.

## 실행 방법

### 다른 컴퓨터에서 처음 실행할 때

Node.js 18 이상과 Python 3.10 이상, Git이 필요합니다. 상품 DB는 저장소에 들어 있어 따로 받지 않습니다.

저장소를 받습니다. 이미 받아 둔 컴퓨터라면 `git clone` 대신 저장소 폴더에서 `git switch main`과 `git pull`을 실행합니다.

```bash
git clone https://github.com/nnujabes/Pick_CU.git
cd Pick_CU
```

저장소 루트에서 처음 한 번만 설치합니다. Python 환경에 FastAPI가 있으면 `pip install`은 건너뛰어도 됩니다.

```bash
pip install -r members/jongho/fastapi/requirements.txt
cd members/hyeokjun/curator_web/frontend
npm install
```

프론트와 백엔드를 한 번에 켭니다.

```bash
npm start
```

- 화면: http://localhost:5173
- API 문서: http://127.0.0.1:8000/docs
- 끄기: 터미널에서 `Ctrl + C`

### 다음부터 실행할 때

저장소 루트에서 최신 코드를 받고 켭니다. `package.json`이나 `requirements.txt`가 바뀌었을 때만 위의 설치를 다시 합니다.

```bash
git pull
cd members/hyeokjun/curator_web/frontend
npm start
```

### 안 될 때

| 증상 | 해결 |
| --- | --- |
| 포트 5173이나 8000을 이미 쓰고 있음 | 먼저 켜 둔 `npm start`를 끄고 다시 실행 |
| `python`을 찾지 못함 | Python 설치 후 터미널을 다시 열기. API 서버는 `python` 명령으로 켜므로 그 이름으로 실행돼야 함 |
| `No module named uvicorn` | `pip install`이 다른 Python에 설치된 경우. `python -m pip install -r members/jongho/fastapi/requirements.txt` 실행 |
| 화면은 뜨는데 추천이 안 됨 | 터미널의 `api` 줄에서 오류 확인. 프론트만 켜는 `npm run dev`로 실행하지 않았는지 확인 |

빌드 명령입니다. API 테스트는 `members/jongho/fastapi/README.md`에 있습니다.

```bash
cd members/hyeokjun/curator_web/frontend
npm run build
```

## 무엇이 진짜이고 무엇이 임시인가

| 항목 | 지금 상태 |
| --- | --- |
| 상품, 가격, 영양 값, 행사 | `cu_products.db`의 실제 값 |
| 점수와 Top 5 | 팀 필터 엔진 `recommend()` 결과 |
| 문장 해석 | **임시.** `members/jongho/fastapi/nlu.py`의 키워드 규칙. A.X 4.0 Light 미연결 |
| 별점과 리뷰 | 실제 입력만 표시. `members/jongho/fastapi/data/reviews.db`에 저장하며 처음에는 전부 "리뷰 없음" |
| 상품 사진 | DB의 `thumbnail_url`을 API에서 `image_url`로 내보내 외부 주소를 그대로 표시. 실패하면 카테고리 대체 이미지 |
| mock 응답 5종 | `frontend/src/mocks/mock_responses.json`. 실제 엔진 결과를 저장한 파일 |

## A.X 연결 방법

`members/jongho/fastapi/nlu.py`의 `parse_request`만 바꾸면 됩니다. 반환하는 `slots`는 `slot_eval/prompts/system_v0.txt`의 출력 스키마와 같습니다. 응답의 `parser` 값도 `"ax"`로 바꿔 주세요.

## 엔진과 설계가 다른 부분

엔진은 수정하지 않았고, 차이는 `members/jongho/fastapi/service.py`에서 다음과 같이 처리합니다.

- **리뷰 점수:** 엔진 부품을 같은 순서로 호출하고 순위를 정하기 전에 `10 × R`을 더합니다. R = (n × 평균 + 5 × 전체평균) ÷ (n + 5) ÷ 5이고, 엔진 총점이 0~100이라 설계의 `0.1 × R`에 100을 곱했습니다. 리뷰가 없으면 결과는 엔진과 같습니다.
- **개수:** 엔진은 고른 카테고리마다 1개씩 묶습니다. "두 개"처럼 말한 개수가 카테고리 수와 다르면 안내 문구만 보여 줍니다.
- **조건 완화:** 엔진에 없어서, 결과가 없을 때 예산을 10% 넓혀 한 번 더 찾습니다.
- **가격대비:** 엔진에 없어서, 나온 Top 5 안에서만 영양 점수 ÷ 합계 순서로 다시 정렬합니다.
- **숫자 조건(`constraints`):** 형식에는 있지만 아직 적용하지 않습니다.

## API

형식은 `api_contract.json`에 있습니다. 프롬프트에 없던 `GET /categories`를 진열대별 상품 수 표시에 쓰려고 추가했습니다.

리뷰는 상품 DB와 분리된 `members/jongho/fastapi/data/reviews.db`에 저장하고 상품 조회 때 `ATTACH`로 붙입니다. 서버 시작 때 자동으로 만들어지고, 상품과는 바코드로만 연결돼 상품 DB를 다시 만들어도 남습니다. 이 파일은 커밋되지 않습니다.

| 경로 | 역할 |
| --- | --- |
| `GET /categories` | 카테고리별 상품 수 |
| `GET /products` | 상품 목록. 카테고리(비우면 전체), 검색, 정렬, 행사, 20개씩 불러오기 |
| `POST /recommend` | 추천. `?mock=single\|combo\|ask\|empty\|relaxed`면 mock 응답 |
| `POST /reviews` | 리뷰 저장. 같은 브라우저의 같은 조합은 수정 |
| `GET /reviews` | 바코드, 조합, 브라우저별 최신 리뷰 |

화면에서는 mock 응답을 쓰지 않습니다. 확인할 때는 API에 `?mock=`을 붙여 호출합니다. DB가 바뀌면 저장소 루트에서 `python members/jongho/fastapi/build_mocks.py`로 다시 만듭니다.

## 폴더 구조

```
curator_web/
├── api_contract.json
└── frontend/src/
    ├── components/           Scene3D, CategoryChips, ChatLog, ResultCard, ShelfDrawer, BasketBar, ReviewDialog 등
    │   ├── scene/            3D 매장. fixtures.tsx의 FIXTURE_MODELS에 경로를 넣으면 glTF로 교체됨
    │   └── ui/               shadcn/ui 방식 컴포넌트
    ├── api/  mocks/  store/  styles/  hooks/  utils/
```

저장소 `.gitignore`의 `lib/` 규칙 때문에 shadcn 기본 경로인 `src/lib`는 커밋되지 않습니다. 그래서 `src/utils/cn.ts`를 씁니다.

`public/store-fallback.png`는 3D를 쓸 수 없는 환경에서 보여 주는 이미지입니다. 모형을 바꾸면 다시 찍어야 합니다.
