# 예산 함수 `budget_filter` 변경과 `budget_too_low` 반영 요청

요청: 종호(jongho) → 하영(hayoung), 혁준(hyeokjun)

## 무엇이 바뀌나

1. 예산 함수 이름이 `extract_budget`에서 `budget_filter`로 바뀝니다.
2. 예산 해석이 아래처럼 바뀝니다.
3. API `status`에 `budget_too_low`가 추가됩니다. 예산이 1000원 미만이면 추천하지 않고 다시 입력하도록 안내합니다.

| 문장 | 지금 | 변경 후 |
| --- | --- | --- |
| `1원으로 먹을 거` | 1 | 1 → 서버가 `budget_too_low` |
| `0원으로 먹을 거` | `None` | 0 → 서버가 `budget_too_low` |
| `0.5원` | 5 | 0 → 서버가 `budget_too_low` |
| `어제 3만원 썼는데 오늘은 야식 추천` | 30000 | `None` (예산 없이 추천) |
| `어제 3만원 썼는데 오늘은 5천원으로` | 30000 | 5000 |
| `1000만원으로 야식`, `99999999999원` | 그 금액 | `None` (예산 없이 추천) |

## 하영에게 요청

`members/hayoung/finetune_v1/code/query_parser.py`에 수정안을 반영해 주세요. 수정안은 `members/jongho/budget_lab/budget_filter.py`입니다. 하영 폴더라 종호가 직접 고치지 않았습니다.

- 함수 이름을 `budget_filter`로 바꾸고, `parse_query`의 호출도 함께 바꿉니다.
- `MAX_BUDGET`, `_SPENT_RE`를 추가하고 `_amount_value`, `_won_amounts`, `budget_filter`의 변경 내용을 옮깁니다.
- `code/check_query_parser.py`의 `qp.extract_budget` 4곳과 `README.md`의 설명을 고칩니다.
- `check_query_parser.py`의 기대값 중 `("0원", None)`은 0으로, `("1,234,000원", 1234000)`은 `None`으로 바뀝니다.

**반영 전까지 앱 동작:** 서버는 `query_parser.py`의 현재 함수를 쓰므로 `budget_too_low`는 1~999원에만 나옵니다. `0원`은 예산 없이 추천하고, `0.5원`은 5원으로 읽어 `budget_too_low`가 됩니다. 지출 금액 제외와 10만원 초과 처리는 적용되지 않습니다.

## 혁준에게 요청

서버가 `budget_too_low`를 보내면 `no_nutrient`처럼 입력창 아래에 안내를 띄워 주세요.

- 제안 문구: "1000원 이상 금액으로 다시 입력해 주세요."
- 응답은 `results: []`, `mode: null`, `quick_replies: []`, `goal: null`입니다. 읽은 금액은 `parsed.budget`에 있습니다.
- `members/hyeokjun/curator_web/api_contract.json`의 `status`에도 추가해 주세요.
- 이 문서를 쓰는 시점에 `main`에서는 `no_nutrient` 화면 처리도 찾지 못했습니다. 함께 확인해 주세요.

## 팀 확인이 필요한 기준

- **최소 금액 1000원(`service.py`의 `MIN_BUDGET`):** DB에는 1000원 미만 상품이 38개 있습니다(최저 300원). 이 기준이면 `900원으로`처럼 입력해도 이 상품들이 예산 안 상품으로 추천되지 않습니다.
- **최대 금액 10만원(`budget_filter.py`의 `MAX_BUDGET`):** 제안 값이며, 초과하면 예산 없이 추천합니다. DB의 최고가 상품은 41,000원입니다.
- **지출 표현:** `썼`, `샀`, `냈`, `날렸`, `벌었`, `결제했`, `지출했`, `나갔`, `들었`이 금액 바로 뒤에 올 때만 제외합니다. `친구가 3만원 줬는데`처럼 목록에 없는 표현은 예산으로 읽습니다.
