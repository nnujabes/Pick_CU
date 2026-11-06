# 인터페이스 약속

팀원끼리 주고받는 함수 이름과 데이터 형식을 적는 문서입니다.
약속을 바꾸면 아래 '변경 기록'에도 함께 적어 주세요.

## 함수 약속

| 함수 이름 | 담당자 | 입력 (이름: 타입) | 출력 (타입) | 사용하는 사람 | 예시 |
| --- | --- | --- | --- | --- | --- |
| `budget_filter` (이전 이름 `extract_budget`) | jongho(수정안), hayoung(`query_parser.py` 반영) | `text`: str | int 또는 None. 0 이상의 예산 상한이며, 상한을 알 수 없거나 10만원을 넘으면 None | hayoung(`parse_query`), jongho(API) | `budget_filter("5천원 이하") == 5000`, `budget_filter("0.5원") == 0`, `budget_filter("1000만원으로") is None` |

## 데이터 형식 약속

| 데이터 이름 | 담당자 | 형식 (예: JSON, CSV) | 필드 (이름: 타입) | 사용하는 사람 | 예시 |
| --- | --- | --- | --- | --- | --- |
| `backend/data/cu_products.db`의 `cu_products` 테이블 | knlee | SQLite | `item_cd`: TEXT(바코드), `category`: TEXT, `product_name`: TEXT, `price`: INTEGER, `event_type`: TEXT(`NONE`, `1+1`, `2+1`), `calories`·`protein`·`sodium`·`carbs`·`sugar`·`fat`: REAL, `thumbnail_url`: TEXT, `exclude_reason`: TEXT 또는 NULL(NULL이면 추천 대상) | jongho(API), 필터 엔진 | `exclude_reason = '소스·양념·조미료'`인 상품은 `search_candidates`와 `recommend` 결과에 나오지 않음 |
| `backend/data/exclude_items.csv` | knlee | CSV | `item_cd`, `category`, `product_name`, `reason` | DB 생성 스크립트 | `8801073910263,식품,삼양)불닭소스200g,소스·양념·조미료` |

## 변경 기록

| 날짜 | 변경한 사람 | 바뀐 항목 | 변경 내용 | 영향받는 사람 |
| --- | --- | --- | --- | --- |
| 2026-11-06 | knlee | `cu_products` 테이블, `search_candidates` | `exclude_reason` 컬럼 추가. 소스·양념·조미료 21개와 식재료 3개(밀가루, 튀김가루, 쌀)를 추천 검색에서 제외. 상품은 DB에 남아 있어 전체 2,154개는 그대로이고, 추천 후보는 2,130개 | jongho(추천 결과, mock 응답), hyeokjun(화면의 추천 결과) |
| 2026-11-06 | jongho | `extract_budget`, `POST /recommend`의 `status` | `extract_budget`의 이름을 `budget_filter`로 변경(수정안은 `members/jongho/budget_lab/budget_filter.py`, 원본 반영은 요청 중). 지출 금액 제외, 10만원 초과는 None, 1원 미만은 0. `status`에 `budget_too_low`(예산 1000원 미만) 추가. 자세한 내용은 `members/jongho/budget_lab/README_budget_filter_반영요청.md` | hayoung(`query_parser.py` 반영), hyeokjun(화면 안내, API 계약) |
