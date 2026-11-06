# 인터페이스 약속

팀원끼리 주고받는 함수 이름과 데이터 형식을 적는 문서입니다.
약속을 바꾸면 아래 '변경 기록'에도 함께 적어 주세요.

## 함수 약속

| 함수 이름 | 담당자 | 입력 (이름: 타입) | 출력 (타입) | 사용하는 사람 | 예시 |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

## 데이터 형식 약속

| 데이터 이름 | 담당자 | 형식 (예: JSON, CSV) | 필드 (이름: 타입) | 사용하는 사람 | 예시 |
| --- | --- | --- | --- | --- | --- |
| `backend/data/cu_products.db`의 `cu_products` 테이블 | knlee | SQLite | `item_cd`: TEXT(바코드), `category`: TEXT, `product_name`: TEXT, `price`: INTEGER, `event_type`: TEXT(`NONE`, `1+1`, `2+1`), `calories`·`protein`·`sodium`·`carbs`·`sugar`·`fat`: REAL, `thumbnail_url`: TEXT, `exclude_reason`: TEXT 또는 NULL(NULL이면 추천 대상) | jongho(API), 필터 엔진 | `exclude_reason = '소스·양념·조미료'`인 상품은 `search_candidates`와 `recommend` 결과에 나오지 않음 |
| `backend/data/exclude_items.csv` | knlee | CSV | `item_cd`, `category`, `product_name`, `reason` | DB 생성 스크립트 | `8801073910263,식품,삼양)불닭소스200g,소스·양념·조미료` |

## 변경 기록

| 날짜 | 변경한 사람 | 바뀐 항목 | 변경 내용 | 영향받는 사람 |
| --- | --- | --- | --- | --- |
| 2026-11-06 | knlee | `cu_products` 테이블, `search_candidates` | `exclude_reason` 컬럼 추가. 소스·양념·조미료 21개와 식재료 3개(밀가루, 튀김가루, 쌀)를 추천 검색에서 제외. 상품은 DB에 남아 있어 전체 2,154개는 그대로이고, 추천 후보는 2,130개 | jongho(추천 결과, mock 응답), hyeokjun(화면의 추천 결과) |
