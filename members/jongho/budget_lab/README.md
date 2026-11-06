# budget_lab

예산 함수 `budget_filter`(이전 이름 `extract_budget`)의 수정안을 시험하는 폴더입니다. 앱이 쓰는 원본은 `members/hayoung/finetune_v1/code/query_parser.py`이고, 이번 수정은 아직 원본에 반영되지 않았습니다(`README_budget_filter_반영요청.md`). FastAPI는 A.X를 쓸 때 원본 함수를, 규칙 파서를 쓸 때 `members/jongho/fastapi/nlu.py`의 `parse_budget`을 씁니다.

검증이 끝나면 변경 내용을 원본에 반영하고 이 폴더는 지웁니다.

평가 결과와 테스트 파일은 저장소 밖 `C:\Users\user\Documents\LLM 프로젝트`에 있습니다.

## 파일

| 파일 | 위치 | 역할 |
| --- | --- | --- |
| `budget_filter.py` | 이 폴더 | 원본 예산 코드의 복사본에 수정 규칙을 적용 |
| `README_budget_filter_반영요청.md` | 이 폴더 | 하영, 혁준에게 보내는 반영 요청 |
| `test_budget_filter.py` | `LLM 프로젝트` | 사례 테스트와 실제 문장 회귀 검사 |
| `evaluate_budget.py` | `LLM 프로젝트` | 원본과 수정안을 같은 문장으로 채점 |
| `budget_lab_수정결과.pdf` | `LLM 프로젝트` | 평가 결과 보고서 |

## 실행

`C:\Users\user\Documents\LLM 프로젝트`에서 실행합니다. GPU와 모델은 필요 없습니다.

```bash
# 테스트
python -m unittest discover -v -s . -p "test_*.py"

# 원본과 수정안 채점
python evaluate_budget.py
```

문장 하나만 확인하려면 다음과 같이 실행합니다. 한글이 깨지면 PowerShell에서 `$env:PYTHONUTF8=1`을 먼저 실행합니다.

```bash
cd members/jongho/budget_lab
python -c "from budget_filter import budget_filter as e; print(e('만원 넘게 써도 돼'))"
```

회귀 검사와 채점은 `members/hayoung`의 원본 코드와 CSV를 읽기만 합니다. #24로 원본에 첫 수정안이 반영되었으므로, 회귀 검사는 학습·개발 문장의 결과가 원본과 같은지 확인합니다. `evaluate_budget.py`의 "수정 전" 값도 지금은 #24 반영본 기준입니다.

## 기준

백엔드는 `budget`을 상한으로만 씁니다. 그래서 상한이 아닌 금액은 쓰지 않고 `None`을 돌려줍니다. `None`은 가격 제한 없음입니다.

- 10만원(`MAX_BUDGET`)을 넘으면 `None`입니다.
- 1원 미만은 0을 돌려줍니다. 1000원 미만 안내(`budget_too_low`)는 `fastapi/service.py`의 `MIN_BUDGET`으로 서버가 판단합니다.

## 코드에서 수정한 부분

금액 계산(`_coef_value`, `_small_value`)과 기존 필터의 기준은 그대로 두었습니다.

| 수정 | 위치 | 내용 |
| --- | --- | --- |
| 금액 후보 전부 찾기 | `_won_amounts`, `_all_amounts` | 첫 금액에서 멈추던 반복문을 모든 금액을 모으도록 변경 |
| 금액 계산 분리 | `_amount_value` | 원본 `extract_budget` 안의 계산을 함수로 분리 |
| "원" 없는 금액 | `_other_amounts`, `_BARE_RE`, `_BUDGET_PREFIX_RE`, `_K_RE`, `_WON_SIGN_RE` | 5천 정도, 예산 6천, 5k, 5,000₩ 인식 |
| 숫자 오인 방지 | `_NUTRIENT_BEFORE_RE`, `_MOVE_AFTER_RE`, `_K_CONTEXT_RE`, `_BUDGET_BEFORE_RE` | 영양 수치, 지명 이동 표현, 10k 마라톤을 금액에서 제외 |
| 상한/하한 | `_UPPER_RE`, `_LOWER_RE` | 넘게·이상·초과는 제외. "이상은 못 써" 같은 상한 표현을 먼저 검사 |
| 말고·대신·빼고 | `_EXCLUDE_RE`, `_SUBTRACT_RE` | 대신, 아니고, 아니라, 빼면, 뺀, 제외 포함 |
| 장수 | `_SHEETS_RE`, `_N`, `_SHEET_COUNT` | 금액 × N장. 지폐·동전이면 N개도 곱함 |
| 범위 | `_RANGE_BETWEEN_RE` | A에서 B, A 내지 B이면 B를 상한으로 사용 |
| 지출 금액 | `_SPENT_RE` | 금액 바로 뒤의 썼·샀·냈 등은 제외. "썼으면"은 예산으로 유지 |
| 금액 범위 | `MAX_BUDGET`, `_amount_value` | 10만원 초과는 `None`. 소수 금액은 내림해 0.5원을 5원으로 다시 읽지 않음 |
| 최종 선택 | `budget_filter` | 남은 금액 중 첫 번째를 반환 |

### 수정 전: 최초 원본 `extract_budget`

```python
def extract_budget(text):
    """문장에서 먼저 나오는 '원' 금액을 양의 정수로 돌려준다. 없으면 None.

    "이내/이하/정도/쯤"과 "N천원대"는 숫자 그대로 쓰고, '원'이 붙지 않은 숫자는 금액으로 보지 않는다.
    """
    if not isinstance(text, str):
        return None
    pos = 0
    while True:
        m = _AMOUNT_RE.search(text, pos)
        if m is None:
            return None
        pos = m.start() + 1
        amount = m.group(0)
        before = text[:m.start()]
        # 한글로 시작하는 금액이 다른 한글에 붙어 있으면 낱말의 일부다: 회사원, 이것만 원해, 몇천원, 단백질만 5천원의 '만 5천'
        if not amount[0].isdigit() and before and _is_hangul(before[-1]):
            continue
        if _VAGUE_BEFORE_RE.search(before):  # 몇 천원, 수 만원
            continue
        # 사원, 일원, 구원처럼 단위 없는 한글 숫자 하나는 금액이 아니다
        if not any(c.isdigit() or c in "십백천만" for c in amount):
            continue
        # 띄어 쓴 "3 원해", "만 원해요"는 금액이 아니라 동사 '원하다'다
        if amount[-2:-1].isspace() and _VERB_AFTER_RE.match(text, m.end()):
            continue
        value = _small_value(m.group("rest"))
        if m.group("man_unit"):
            man = m.group("man").strip()
            value += (_small_value(man) if man else 1) * 10000
        if value > 0 and value == int(value):
            return int(value)
```

### 수정 후: `budget_filter`

```python
def budget_filter(text):
    """문장에서 예산 상한을 0 이상의 정수로 돌려준다. 상한을 알 수 없거나 MAX_BUDGET을 넘으면 None."""
    if not isinstance(text, str):
        return None
    amounts = _all_amounts(text)
    usable, excluded, has_lower = [], [], False
    for index, (value, _start, end) in enumerate(amounts):
        after = text[end:]
        if index + 1 < len(amounts) and _RANGE_BETWEEN_RE.match(text[end:amounts[index + 1][1]]):
            continue  # 범위는 뒤 금액을 상한으로 쓴다
        if _EXCLUDE_RE.match(after):
            excluded.append(value)
            continue
        if _SUBTRACT_RE.match(after) or _SPENT_RE.match(after):
            continue
        # 상한 표현을 먼저 본다: "4천원 넘게 쓰면 다 남겨요"는 상한이다
        if not _UPPER_RE.match(after) and _LOWER_RE.match(after):
            has_lower = True
            continue
        sheets = _SHEETS_RE.match(after)
        if sheets:
            count = sheets.group(1) or sheets.group(2)
            value *= int(count) if count.isdigit() else _SHEET_COUNT[count]
        usable.append(value)
    if usable:
        budget = usable[0]
    elif has_lower or not excluded:
        return None
    else:
        budget = excluded[0]
    return budget if budget <= MAX_BUDGET else None
```

### 새로 추가한 패턴

```python
# 금액 바로 뒤의 표현
_PARTICLE = r"^\s*(?:은|는|이|가|을|를)?\s*"
_UPPER_RE = re.compile(_PARTICLE + r"(?:안\s*넘|못\s*넘|넘지|넘기지|넘기기|넘기면|넘으면|넘어가면|넘게\s*쓰면"
                                   r"|넘는\s*(?:건|거|것)\S*\s*(?:빼고|말고|안|싫)"
                                   r"|이상(?:은|을)?\s*(?:못|안\s*돼|안돼|힘들|어렵|무리|부담|곤란))")
_LOWER_RE = re.compile(_PARTICLE + r"(?:넘게|넘어도|넘는|넘어|이상|초과|부터)")
_EXCLUDE_RE = re.compile(r"^\s*(?:짜리|어치)?\s*(?:은|는|이|가)?\s*(?:[가-힣]+\s+)?(?:말고|대신|아니고|아니라)")
_SUBTRACT_RE = re.compile(_PARTICLE + r"(?:빼고|빼면|뺀|제외)")
_SPENT_RE = re.compile(r"^\s*(?:짜리|어치)?\s*(?:은|는|이|가|을|를|이나|나)?\s*"
                       r"(?:썼|샀|냈|날렸|벌었|결제했|지출했|나갔|들었)(?!으면)")
_N = r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|\d+)"
_SHEETS_RE = re.compile(r"^\s*(?:짜리)?\s*(?:(?:지폐|동전)\s*" + _N + r"\s*(?:장|개)|" + _N + r"\s*장)")
_RANGE_BETWEEN_RE = re.compile(r"^\s*(?:에서|부터|내지|~|-|–)\s*$")
_SHEET_COUNT = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}

# '원'이 없는 금액: 뒤에 예산 표현이 올 때만 인정한다.
_BARE_AMOUNT = rf"\d+\s*만(?:\s*(?:\d+\s*)?천)?|(?:[{_D}]?만\s*)?(?:\d+|[{_D}])\s*천(?:\s*\d+\s*백)?"
_BARE_RE = re.compile(rf"(?<![\d가-힣,.])({_BARE_AMOUNT})"
                      r"(?=\s*(?:정도|쯤|으로|이하|이내|까지|안쪽|안에서|미만|선에서|사이|안\s*넘|못\s*넘|넘지|넘기지))")
_BUDGET_PREFIX_RE = re.compile(rf"예산\s*(?:은|는|이|가|을|를)?\s*({_BARE_AMOUNT})(?!\s*원|\d)")
_NUTRIENT_BEFORE_RE = re.compile(r"(?:칼로리|열량|나트륨|당류|단백질|지방|탄수화물|kcal)\s*(?:은|는|이|가|을|를|도)?\s*$", re.I)
_MOVE_AFTER_RE = re.compile(r"^\s*으로\s*(?:[가-힣]+\s+)?(?:출장|여행|이사|놀러|가는|가요|간다|갔|왔)")
_K_CONTEXT_RE = re.compile(r"^\s*(?:정도|쯤|으로|로|이하|이내|까지|안쪽|안에서|미만|선에서|안\s*넘|못\s*넘|넘지|넘기지)")
_BUDGET_BEFORE_RE = re.compile(r"예산\s*(?:은|는|이|가|을|를)?\s*$")
_K_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[kK](?![a-zA-Z])")
_WON_SIGN_RE = re.compile(r"₩\s*(\d[\d,]*)|(\d[\d,]*)\s*₩")
```

### 금액 계산 분리: `_amount_value`

```python
def _amount_value(m):
    value = _small_value(m.group("rest"))
    if m.group("man_unit"):
        man = m.group("man").strip()
        value += (_small_value(man) if man else 1) * 10000
    return int(value)  # 0.5원은 5원으로 다시 읽지 않고 0으로 돌려준다. 금액이 너무 작은지는 호출하는 쪽이 정한다.
```

### 금액 후보 전부 찾기: `_won_amounts`, `_all_amounts`

걸러 내는 기준은 원본과 같습니다.

```python
def _won_amounts(text):
    """'원'이 붙은 금액을 (값, 시작, 끝)으로 모두 찾는다. 걸러 내는 기준은 원본과 같다."""
    found, pos = [], 0
    while True:
        m = _AMOUNT_RE.search(text, pos)
        if m is None:
            return found
        amount, before = m.group(0), text[:m.start()]
        value = _amount_value(m)
        rejected = (
            # 한글로 시작하는 금액이 다른 한글에 붙어 있으면 낱말의 일부다: 회사원, 이것만 원해, 몇천원, 단백질만 5천원의 '만 5천'
            (not amount[0].isdigit() and before and _is_hangul(before[-1]))
            or _VAGUE_BEFORE_RE.search(before)  # 몇 천원, 수 만원
            # 사원, 일원, 구원처럼 단위 없는 한글 숫자 하나는 금액이 아니다
            or not any(c.isdigit() or c in "십백천만" for c in amount)
            # 띄어 쓴 "3 원해", "만 원해요"는 금액이 아니라 동사 '원하다'다
            or (amount[-2:-1].isspace() and _VERB_AFTER_RE.match(text, m.end()))
        )
        if rejected:
            pos = m.start() + 1
            continue
        found.append((value, m.start(), m.end()))
        pos = m.end()
```

```python
def _all_amounts(text):
    """위치 순서로 돌려준다. 겹치면 긴 쪽만 남긴다."""
    amounts = sorted(set(_won_amounts(text) + _other_amounts(text)), key=lambda a: (a[1], a[1] - a[2]))
    kept = []
    for amount in amounts:
        if not kept or amount[1] >= kept[-1][2]:
            kept.append(amount)
    return kept
```

### "원" 없는 금액 찾기: `_other_amounts`

```python
def _other_amounts(text):
    """'원' 없이 쓴 금액(5천 정도, 예산 5k, 5,000₩)을 찾는다."""
    found = []
    for m in list(_BARE_RE.finditer(text)) + list(_BUDGET_PREFIX_RE.finditer(text)):
        if _NUTRIENT_BEFORE_RE.search(text[:m.start(1)]):
            continue  # 칼로리 5천 이하, 나트륨 2천 이하
        if not m.group(1)[0].isdigit() and _MOVE_AFTER_RE.match(text[m.end(1):]):
            continue  # 이천으로 출장, 사천으로 여행
        won = _AMOUNT_RE.fullmatch(m.group(1) + "원")
        value = _amount_value(won) if won else None
        if value:
            found.append((value, m.start(1), m.end(1)))
    for m in _K_RE.finditer(text):
        value = float(m.group(1)) * 1000
        if not (_BUDGET_BEFORE_RE.search(text[:m.start()]) or _K_CONTEXT_RE.match(text[m.end():])):
            continue  # 10k 마라톤
        if value > 0 and value == int(value):
            found.append((int(value), m.start(), m.end()))
    for m in _WON_SIGN_RE.finditer(text):
        found.append((int((m.group(1) or m.group(2)).replace(",", "")), m.start(), m.end()))
    return found
```

## 알려진 한계

| 문장 | 결과 | 비고 |
| --- | --- | --- |
| 2천으로 제한된 나트륨 | 2,000 | 영양 낱말이 금액 뒤에 있어 금액으로 읽음. 의도는 `None` |
| 오천 정도 걸었어 | 5,000 | 문맥을 봐야 금액이 아님을 알 수 있음. 의도는 `None` |
| 1500원짜리 음료 2개 | 1,500 | "장"과 지폐·동전이 아니면 곱하지 않음 |
| 만원짜리 도시락 말고 싼 거 | 10,000 | "미만"처럼 경계값을 그대로 씀 |
| 친구가 3만원 줬는데 | 30,000 | 목록에 있는 지출 표현만 제외하며, 예산인지는 문맥으로만 알 수 있음 |

영양 낱말과 이동 낱말은 목록에 있는 표현만 막습니다.
