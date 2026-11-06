"""query_parser.extract_budget 수정안을 시험하는 복사본. 앱은 이 파일을 쓰지 않는다.

원본: members/hayoung/finetune_v1/code/query_parser.py
검증이 끝나면 변경 내용을 원본에 반영하고 이 폴더는 지운다.
budget은 상한으로만 쓰이므로, 상한이 아닌 금액은 쓰지 않고 None을 돌려준다.
"""
import re

_HAN_DIGIT = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_D = "".join(_HAN_DIGIT)
_NUM = r"\d+(?:,\d+)*(?:\.\d+)?"
_COEF = rf"(?:{_NUM}\s*|[{_D}])?"
# 1만 미만 수: 7천5백, 삼천오백, 5000, 2.5 ...
_SMALL = rf"(?:{_COEF}천\s*)?(?:{_COEF}백\s*)?(?:{_COEF}십\s*)?(?:{_NUM}|[{_D}])?"
_AMOUNT_RE = re.compile(rf"(?=[\d{_D}십백천만])(?:(?P<man>{_SMALL})(?P<man_unit>만)\s*)?(?P<rest>{_SMALL})\s*원")
_SMALL_PART_RE = re.compile(rf"(?:(?P<c>{_COEF})천\s*)?(?:(?P<b>{_COEF})백\s*)?(?:(?P<s>{_COEF})십\s*)?(?P<o>{_NUM}|[{_D}])?")
_VAGUE_BEFORE_RE = re.compile(r"(?:몇|수|수십|수백|여러)\s*$")
_VERB_AFTER_RE = re.compile(r"하|해|합|했|할|함|한(?:다|데|는|게|거|것)")

# 금액 바로 뒤의 표현
_PARTICLE = r"^\s*(?:은|는|이|가|을|를)?\s*"
_UPPER_RE = re.compile(_PARTICLE + r"(?:안\s*넘|못\s*넘|넘지|넘기지|넘기기|넘기면|넘으면|넘어가면|넘게\s*쓰면"
                                   r"|넘는\s*(?:건|거|것)\S*\s*(?:빼고|말고|안|싫)"
                                   r"|이상(?:은|을)?\s*(?:못|안\s*돼|안돼|힘들|어렵|무리|부담|곤란))")
_LOWER_RE = re.compile(_PARTICLE + r"(?:넘게|넘어도|넘는|넘어|이상|초과|부터)")
_EXCLUDE_RE = re.compile(r"^\s*(?:짜리|어치)?\s*(?:은|는|이|가)?\s*(?:[가-힣]+\s+)?(?:말고|대신|아니고|아니라)")
_SUBTRACT_RE = re.compile(_PARTICLE + r"(?:빼고|빼면|뺀|제외)")
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


def _is_hangul(ch):
    return "가" <= ch <= "힣"


def _coef_value(token, default=1):
    token = (token or "").strip()
    if not token:
        return default
    if token in _HAN_DIGIT:
        return _HAN_DIGIT[token]
    return float(token.replace(",", ""))


def _small_value(s):
    m = _SMALL_PART_RE.fullmatch(s.strip())
    total = 0.0
    for key, unit in (("c", 1000), ("b", 100), ("s", 10)):
        if m.group(key) is not None:  # 단위가 있으면 계수가 빈 문자열이어도 None이 아니다 ("천" = 1000)
            total += _coef_value(m.group(key)) * unit
    total += _coef_value(m.group("o"), default=0)
    return total


def _amount_value(m):
    value = _small_value(m.group("rest"))
    if m.group("man_unit"):
        man = m.group("man").strip()
        value += (_small_value(man) if man else 1) * 10000
    return int(value) if value > 0 and value == int(value) else None


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
            or value is None
        )
        if rejected:
            pos = m.start() + 1
            continue
        found.append((value, m.start(), m.end()))
        pos = m.end()


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


def _all_amounts(text):
    """위치 순서로 돌려준다. 겹치면 긴 쪽만 남긴다."""
    amounts = sorted(set(_won_amounts(text) + _other_amounts(text)), key=lambda a: (a[1], a[1] - a[2]))
    kept = []
    for amount in amounts:
        if not kept or amount[1] >= kept[-1][2]:
            kept.append(amount)
    return kept


def extract_budget(text):
    """문장에서 예산 상한을 양의 정수로 돌려준다. 상한을 알 수 없으면 None."""
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
        if _SUBTRACT_RE.match(after):
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
        return usable[0]
    if has_lower or not excluded:
        return None
    return excluded[0]
