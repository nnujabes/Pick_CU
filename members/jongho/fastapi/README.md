# Pick CU API (FastAPI)

웹 화면(`members/hyeokjun/curator_web/frontend`, `members/hyeokjun/curator_web2`)이 호출하는 API 서버입니다. 팀 필터 엔진(`backend/pickcu/`)과 상품 DB(`backend/data/cu_products.db`)는 읽기만 합니다.

## 실행

```bash
pip install -r members/jongho/fastapi/requirements.txt
python -m uvicorn main:app --app-dir members/jongho/fastapi --port 8000
```

API 문서는 http://127.0.0.1:8000/docs 에서 볼 수 있습니다. 화면과 함께 켜려면 `members/hyeokjun/curator_web/frontend`(http://localhost:5173) 또는 `members/hyeokjun/curator_web2`(http://localhost:5174)에서 `npm start`를 실행합니다. 두 화면을 함께 쓸 때는 API 포트(8000)가 겹치므로 두 번째 화면은 `npm run dev`로 띄웁니다.

### 문장 해석 (A.X)

서버는 시작할 때 A.X를 한 번 불러옵니다. 불러오지 못하면 오류 없이 규칙 파서(`nlu.py`)로 동작하고, 응답의 `parser`가 `rule`이 됩니다.

- NVIDIA GPU 메모리 약 5GB 이상, CUDA용 torch, `members/hayoung/finetune_v1/requirements.txt`(transformers, peft, bitsandbytes, accelerate)가 필요합니다. Windows는 bitsandbytes 설치가 어려워 WSL·Linux를 권합니다.
- 어댑터 `adapter_model.safetensors`는 git에 없어서 따로 받아 `members/hayoung/finetune_v1/adapter/best/`에 넣습니다. 다른 곳에 두었으면 `QUERY_PARSER_ADAPTER`로 경로를 지정합니다. sha256 `f95d9f5e429f0f16c854c769253ee0dd4df075f91b5ea3cc29fd56b7b157cc8b`
- 첫 실행 때 `skt/A.X-4.0-Light` 원본(약 15GB)을 받습니다. 모델 로딩은 서버 시작 때 한 번 하고, 이후 문장 하나에 약 3초 걸립니다(RTX 4060 기준).
- GPU 없이 실행: `PICKCU_PARSER=rule`

`npm start`는 그 환경의 `python`으로 API를 띄웁니다. Windows Python에 위 패키지가 없으면 규칙 파서로 동작하므로, A.X를 쓰려면 WSL에서 위 실행 명령으로 API를 띄우고 화면은 `npm run dev`로 켭니다.

## 테스트

```bash
python -m unittest discover -s members/jongho/fastapi -p "test_*.py"
```

기존 테스트는 규칙 파서 기준이라 GPU 없이 돕니다. A.X 테스트는 모델을 불러오지 못하면 건너뜁니다.

## 파일

| 파일 | 역할 |
| --- | --- |
| `main.py` | API 경로. 응답 형식의 기준은 이 README의 API 명세서 |
| `service.py` | 문장 해석 선택(A.X 또는 규칙), 팀 엔진과 상품 DB 호출, 응답 형식 변환, 리뷰 점수 반영 |
| `nlu.py` | 규칙 파서. A.X를 쓸 수 없을 때의 해석과 개수·가성비 해석 |
| `review_store.py` | 리뷰 저장. `data/reviews.db`는 자동으로 만들어지고 커밋되지 않음 |
| `build_mocks.py` | 프론트의 `mock_responses.json` 생성 |
| `test_api.py` | API 테스트 |

## API 명세서

### 공통

- 기본 주소: `http://127.0.0.1:8000`
- 요청과 응답 본문은 JSON입니다. 인증은 없습니다.
- 브라우저에서 직접 호출(CORS)하는 것은 `http://localhost:5173`, `http://127.0.0.1:5173`만 허용합니다. 두 웹 화면은 Vite 프록시(`/api`)를 거쳐 호출하므로 이 제한을 받지 않습니다.
- 영양 값 단위는 `calories` kcal, `sodium` mg, 나머지(`protein`, `carbs`, `sugar`, `fat`) g입니다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/categories` | 카테고리 목록과 상품 수 |
| GET | `/products` | 상품 목록 조회, 검색, 정렬 |
| POST | `/recommend` | 문장과 카테고리로 상품 추천 |
| POST | `/reviews` | 리뷰 저장 또는 수정 |
| GET | `/reviews` | 리뷰 목록 조회 |

오류 응답은 다음과 같습니다.

| 코드 | 상황 | `detail` 형식 |
| --- | --- | --- |
| 400 | 없는 카테고리, 중복 카테고리, 없는 상품 | 문자열. 예: `"없는 카테고리입니다: 없음"` |
| 422 | 필드 누락, 길이나 범위 초과, 허용되지 않은 값 | FastAPI 검증 오류 배열 |

### 공통 형식

**Product**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `item_cd` | string | 바코드 |
| `category` | string | `간편식사`, `즉석조리`, `과자류`, `아이스크림`, `식품`, `음료` 중 하나 |
| `product_name` | string | 상품명 |
| `price` | integer | 가격(원) |
| `event_type` | string | `NONE`, `1+1`, `2+1` 중 하나 |
| `calories`, `protein`, `sodium`, `carbs`, `sugar`, `fat` | number | 영양 값 |
| `image_url` | string \| null | 상품 이미지 외부 URL |

**Parsed** (문장을 해석한 결과)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `nutrients` | object | `calories`, `carbs`, `protein`, `fat`, `sugar`, `sodium`별로 `high`, `low`, `null` 중 하나 |
| `constraints` | array | 수치 조건 `{nutrient, op, value}`. 현재 규칙 파서는 항상 `[]` |
| `budget` | integer \| null | 예산(원) |
| `count` | integer \| null | 문장에서 요청한 개수 |
| `price_priority` | boolean | 가성비 요청 여부 |
| `need_clarification` | boolean | 되물어야 하는지 여부 |
| `clarification_question` | string \| null | 되묻는 문장 |
| `issue` | string \| null | `category_conflict`, `out_of_scope`, `null` 중 하나. 현재 규칙 파서는 항상 `null` |

### GET /categories

카테고리별 상품 수와 전체 상품 수를 돌려줍니다.

```json
{
  "categories": [
    { "name": "간편식사", "count": 199 },
    { "name": "즉석조리", "count": 40 },
    { "name": "과자류", "count": 627 },
    { "name": "아이스크림", "count": 109 },
    { "name": "식품", "count": 768 },
    { "name": "음료", "count": 411 }
  ],
  "total": 2154
}
```

### GET /products

쿼리 파라미터는 모두 선택입니다.

| 이름 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `category` | string | `""` | 카테고리. 비우면 전체, 없는 값이면 400 |
| `q` | string | `""` | 상품명 부분 검색. 최대 50자 |
| `sort` | string | `default` | 정렬 기준(아래 표) |
| `promo` | string | `""` | `1+1` 또는 `2+1`. 비우면 전체 |
| `page` | integer | `1` | 1 이상 |
| `size` | integer | `20` | 1~100 |

| `sort` 값 | 정렬 |
| --- | --- |
| `default` | 상품명 오름차순 |
| `price` | 가격 낮은 순 |
| `protein` | 단백질 많은 순 |
| `sugar` | 당류 적은 순 |
| `calories` | 칼로리 낮은 순 |
| `sodium` | 나트륨 적은 순 |

응답의 `items`는 Product에 `avg_rating`(number \| null), `n_reviews`(integer)를 더한 형식입니다. 페이지가 범위를 넘으면 `total`은 그대로이고 `items`만 비어 있습니다.

요청 예시: `GET /products?category=음료&sort=price&size=1`

```json
{
  "total": 411,
  "page": 1,
  "size": 1,
  "items": [
    {
      "item_cd": "8801104250283",
      "category": "음료",
      "product_name": "빙그레)쥬시쿨자두180ml",
      "price": 600,
      "event_type": "NONE",
      "calories": 44.0,
      "protein": 0.0,
      "sodium": 115.0,
      "carbs": 11.0,
      "sugar": 8.6,
      "fat": 0.0,
      "image_url": "https://tqklhszfkvzk6518638.edge.naverncp.com/product/8801104250283_1.png",
      "avg_rating": null,
      "n_reviews": 0
    }
  ]
}
```

### POST /recommend

응답 형식의 기준은 이 README입니다. `members/hyeokjun/curator_web/api_contract.json`은 더 이상 갱신하지 않습니다.

쿼리 파라미터 `mock`(선택)에 `single`, `combo`, `ask`, `empty`, `relaxed` 중 하나를 주면 `mock_responses.json`의 응답을 그대로 돌려줍니다. 이때도 본문은 아래 형식을 지켜야 합니다.

| 요청 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `text` | string | O | 사용자 문장. 1~300자 |
| `categories` | string[] | O | 카테고리 1~3개. 중복 불가 |
| `pending_text` | string \| null | | 되묻기에 답할 때 넣는 직전 문장. 최대 300자 |

```json
{
  "text": "운동 후에 먹을 거 8천원",
  "categories": ["간편식사", "음료"]
}
```

| 응답 필드 | 타입 | 설명 |
| --- | --- | --- |
| `status` | string | `ok`, `ask`, `empty`, `no_nutrient`, `budget_too_low` 중 하나(아래 표) |
| `parsed` | Parsed | 문장 해석 결과 |
| `goal` | string \| null | `다이어트`, `근력`, `벌크업`, `운동 후` 중 하나 |
| `quick_replies` | string[] | 되물을 때 보여 줄 답변 버튼 |
| `mode` | string \| null | 상품 1개씩이면 `단품`, 여러 개 묶음이면 `조합`, 결과가 없으면 `null` |
| `relaxed` | object \| null | 예산을 넓혔을 때 `{message, original_budget, used_budget}` |
| `notice` | string \| null | 요청 개수와 카테고리 수가 다를 때의 안내 문장 |
| `results` | array | 추천 결과. 최대 5개 |
| `source` | string | 실제 추천은 `db`, mock은 `mock` |
| `parser` | string | 문장 해석기. A.X 결과면 `ax`, 규칙 파서 결과면 `rule` |
| `reason` | string \| null | `no_nutrient`의 이유(아래 표). 항상 들어가며, 다른 `status`에서는 `null`. `mock` 응답에는 없을 수 있음 |

| `status` | 의미 | 화면 처리 |
| --- | --- | --- |
| `ok` | 추천 성공 | `results` 표시 |
| `ask` | 규칙 파서의 해석 결과에 영양 조건이 없음. 예산만 있어도 되묻고, 운동 종류나 다이어트 여부는 묻지 않음. A.X를 쓰는 동안에는 나오지 않음 | `parsed.clarification_question`과 `quick_replies`를 보여 주고, 답을 `text`로, 직전 문장을 `pending_text`로 다시 요청 |
| `empty` | 조건에 맞는 상품 없음 | 결과 없음 안내 |
| `no_nutrient` | A.X가 문장에서 영양소 정보를 찾지 못함(`parse_query`가 `None`). 이유는 `reason` | 입력창 아래에 다시 입력하라는 안내를 표시. `results`는 빈 배열 |
| `budget_too_low` | 예산이 1000원 미만. `no_nutrient`를 먼저 확인하고, 되묻기보다 먼저 나옴 | 입력창 아래에 최소 금액 안내를 표시. `results`는 빈 배열, 읽은 금액은 `parsed.budget`. `service.py`의 `MIN_BUDGET`을 바꾸면 화면 값도 같이 바꿔야 함 |

| `reason` | 뜻 | 화면 문구 |
| --- | --- | --- |
| `empty` | 빈 입력 | 문장을 입력해 주세요. |
| `too_long` | 300자 초과 | 문장이 너무 길어요. 300자 이내로 줄여 주세요. |
| `no_condition` | 인삿말·잡담·일반 요청어만 있음 | 인사나 추천 요청만으로는 찾을 수 없어요. 상황이나 원하는 영양을 적어 주세요. |
| `unrelated` | 모델이 관계없는 문장으로 판단 | 먹거리와 관련 없는 문장이에요. 상황이나 원하는 영양을 적어 주세요. |
| `invalid_output` | 모델 출력 형식 오류 | 문장을 이해하지 못했어요. 조금 다르게 적어 주세요. |
| `error` | 실행 중 예외 | 문장을 해석하다 문제가 생겼어요. 다시 시도해 주세요. |
| `null` | 이유 모름 | 영양소 정보를 알 수 없어요. 다시 입력해 주세요. |

이유는 하영의 `query_parser.parse_query_with_reason`이 돌려주는 값을 그대로 담습니다. 이 함수가 없으면 `parse_query`로 대신하고 `reason`은 `null`입니다.

`results`의 각 항목은 다음과 같습니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `rank` | integer | 순위. 1부터 |
| `total_score` | number | 총점. 순위 기준이며 리뷰 점수가 더해지면 100을 넘을 수 있음 |
| `nutrition_score` | number | 영양 점수 |
| `price_score` | number \| null | 가격 점수. 예산이 없거나 카테고리가 1개면 `null` |
| `total_price` | integer | 합계 가격(원) |
| `items` | array | Product에 `nutrition_score`, `avg_rating`, `n_reviews`를 더한 형식. 카테고리마다 1개 |
| `totals` | object | 영양 값 6종의 합계 |

응답 예시(`results`는 5개 중 1위만 표시):

```json
{
  "status": "ok",
  "parsed": {
    "nutrients": {
      "calories": null,
      "carbs": null,
      "protein": "high",
      "fat": "low",
      "sugar": "low",
      "sodium": null
    },
    "constraints": [],
    "budget": 8000,
    "count": null,
    "price_priority": false,
    "need_clarification": false,
    "clarification_question": null,
    "issue": null
  },
  "goal": "운동 후",
  "quick_replies": [],
  "mode": "조합",
  "relaxed": null,
  "notice": null,
  "results": [
    {
      "rank": 1,
      "total_score": 84.3,
      "nutrition_score": 82.3,
      "price_score": 88.8,
      "total_price": 7100,
      "items": [
        {
          "item_cd": "8800271905514",
          "category": "간편식사",
          "product_name": "샌)급식대가저당치킨샌드",
          "price": 3600,
          "event_type": "NONE",
          "calories": 338.0,
          "protein": 26.0,
          "sodium": 810.0,
          "carbs": 45.0,
          "sugar": 4.0,
          "fat": 6.0,
          "nutrition_score": 82.2,
          "image_url": "https://tqklhszfkvzk6518638.edge.naverncp.com/product/8800271905514_1.png",
          "avg_rating": null,
          "n_reviews": 0
        },
        {
          "item_cd": "8806006516413",
          "category": "음료",
          "product_name": "유한)비컴플런부스터110ml",
          "price": 3500,
          "event_type": "1+1",
          "calories": 92.0,
          "protein": 9.0,
          "sodium": 10.0,
          "carbs": 14.0,
          "sugar": 0.0,
          "fat": 0.0,
          "nutrition_score": 82.4,
          "image_url": "https://tqklhszfkvzk6518638.edge.naverncp.com/product/8806006516413.jpg",
          "avg_rating": null,
          "n_reviews": 0
        }
      ],
      "totals": {
        "calories": 430.0,
        "protein": 35.0,
        "sodium": 820.0,
        "carbs": 59.0,
        "sugar": 4.0,
        "fat": 6.0
      }
    }
  ],
  "source": "db",
  "parser": "rule",
  "reason": null
}
```

동작 규칙은 다음과 같습니다.

- **예산 완화**: 예산 안에 결과가 없으면 예산의 1.1배로 한 번 더 찾고, 찾으면 `relaxed`를 채웁니다. 그래도 없으면 `empty`입니다.
- **가성비**: `price_priority`가 `true`이면 Top 5 안에서만 `nutrition_score ÷ total_price` 순서로 다시 놓고 `rank`를 새로 매깁니다.
- **개수**: 추천은 카테고리마다 1개씩 담습니다. 문장의 개수가 카테고리 수와 달라도 결과 개수는 바뀌지 않고 `notice`로 안내합니다.
- **리뷰 점수**: 조합의 `total_score`에 `10 × (상품별 R의 평균)`을 더합니다. `R = (n × 평균 + 5 × 전체평균) ÷ (n + 5) ÷ 5`이고, 리뷰가 없는 상품의 R은 `전체평균 ÷ 5`입니다. 저장된 리뷰가 하나도 없으면 점수를 더하지 않습니다.
- **검사 순서**: 카테고리 값은 문장 해석 뒤에 검사합니다. 그래서 `ask`, `no_nutrient`, `budget_too_low`로 끝나는 요청은 없는 카테고리가 있어도 200을 돌려줍니다.
- **A.X 해석**: 영양소 2개는 A.X가, 예산은 `extract_budget`이, 개수와 가성비는 규칙 파서가 정합니다. `goal`은 `null`입니다. 모델을 쓸 수 없으면 규칙 파서 결과를 쓰고, 해석 결과가 `None`이면(300자 초과, 출력 형식 오류 포함) `no_nutrient`를 돌려줍니다.
- **A.X의 한계**: 해석에 성공하면 항상 영양소 2개를 내므로 되묻지 않습니다. 인삿말과 관계없는 문장은 대부분 `no_nutrient`가 되지만(PR #28), "비건인데 먹을 거 있어?", "돼지고기 빼고 추천해줘"처럼 빼 달라는 조건은 반영하지 못한 채 추천이 나옵니다.
- **운동 판별 (규칙 파서)**: 문장에 "운동"이 있으면 운동 후(단백질 높게, 지방 낮게, 당류 낮게)로 해석합니다. "운동하기 전" 같은 운동 전 표현은 탄수화물 높게로 해석하고, "운동 안", "운동화" 같은 표현은 운동 후로 보지 않습니다. 다른 영양 조건이 없으면 되묻습니다.
- **규칙 파서의 한계**: 키워드로만 판별해서 "운동 전부 끝났어"는 운동 전으로, "오늘 운동 쉬었어"는 운동 후로, "운동화 벗고 운동 끝났어"는 운동이 아닌 것으로 해석합니다. "1만원 미만"은 "1만원 이하"와 같이 예산 10000으로 처리하며, 예산 완화가 적용되면 그 이상도 나올 수 있습니다.

### POST /reviews

같은 `session_id`와 같은 상품 묶음의 리뷰가 이미 있으면 새로 만들지 않고 수정합니다. 상품 순서와 중복은 구분하지 않습니다.

| 요청 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `barcodes` | string[] | O | 바코드 1~30개. 없는 상품이 있으면 400 |
| `rating` | integer | O | 별점 1~5 |
| `comment` | string | | 최대 200자. 기본값 `""` |
| `query_text` | string \| null | | 추천받을 때 쓴 문장. 최대 600자 |
| `parsed_json` | any | | 추천받을 때의 해석 결과. 저장만 하고 `GET /reviews`로는 돌려주지 않음 |
| `session_id` | string | O | 클라이언트가 만드는 세션 식별자. 8~64자 |

```json
{
  "barcodes": ["8801104250283"],
  "rating": 5,
  "comment": "좋아요",
  "session_id": "session-0001"
}
```

응답의 `product_stats`는 저장 후 다시 계산한 상품별 별점입니다.

```json
{
  "review_id": 1,
  "product_stats": [
    { "barcode": "8801104250283", "avg_rating": 5.0, "n_reviews": 1 }
  ]
}
```

### GET /reviews

최근에 작성하거나 수정한 순서로 돌려줍니다. 필터를 여러 개 주면 모두 만족하는 리뷰만 나옵니다.

| 쿼리 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `barcode` | string | `""` | 이 상품이 포함된 리뷰 |
| `combo_key` | string | `""` | 상품 묶음. 바코드를 정렬해 `\|`로 이은 값 |
| `session_id` | string | `""` | 이 세션이 쓴 리뷰 |
| `limit` | integer | `20` | 1~100 |

응답 예시입니다. 시각은 UTC이고, `updated_at`은 수정한 적이 없으면 `null`입니다. 상품 DB에서 사라진 상품의 리뷰도 남아 있으며, 이때 `items`의 `product_name`, `image_url`, `category`는 `null`입니다.

```json
{
  "items": [
    {
      "id": 1,
      "combo_key": "8801104250283",
      "rating": 5,
      "comment": "좋아요",
      "query_text": null,
      "created_at": "2026-11-05 05:48:00",
      "updated_at": null,
      "barcodes": ["8801104250283"],
      "items": [
        {
          "barcode": "8801104250283",
          "product_name": "빙그레)쥬시쿨자두180ml",
          "image_url": "https://tqklhszfkvzk6518638.edge.naverncp.com/product/8801104250283_1.png",
          "category": "음료"
        }
      ]
    }
  ]
}
```
