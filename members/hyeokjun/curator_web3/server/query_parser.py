"""사용자 문장 → DB 조회용 조건 JSON 변환 (추론 전용).

    parse_query("5천원 이하로 운동 후에 먹을 거")
    → {"budget": 5000, "nutrients": {"단백질": "high", "지방": "low"}}

- 영양소 2개와 방향은 양자화한 A.X-4.0-Light(Ollama)가, 예산은 일반 코드(extract_budget)가 뽑는다.
- members/hayoung/finetune_v1/code/query_parser.py의 복사본이며, 모델 호출 부분만 Ollama로 바꿨다.
- 모델에는 시스템 프롬프트와 사용자 문장만 넣는다.
- 모델: 환경변수 OLLAMA_MODEL, 기본값 pickcu-ax:q5_k_m. 주소: 환경변수 OLLAMA_URL.

CLI (curator_web3/server 에서 실행):
    python -m query_parser "5천원 이하로 운동 후에 먹을 거"
"""
import hashlib
import json
import logging
import os
import re
import sys
import urllib.request

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "pickcu-ax:q5_k_m")
KEEP_ALIVE = "30m"
MAX_NEW_TOKENS = 128
MAX_INPUT_CHARS = 300  # 이보다 긴 입력은 모델을 부르지 않고 None

# 학습(ft_data) 때 쓴 프롬프트. check_query_parser.py가 ft_data와 글자까지 같은지 확인한다.
TRAIN_SYSTEM_PROMPT = """당신은 편의점 영양 추천 도우미입니다. 사용자 문장을 보고 필요한 영양소 2개와 방향(높음/낮음)을 JSON으로만 답하세요.

출력 형식: {"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "fat", "direction": "low"}]}
성분: calories, protein, sodium, carbs, sugar, fat
방향: high, low
성분은 반드시 위 6개(calories, protein, sodium, carbs, sugar, fat) 중에서만 고르세요. 다른 영양소는 쓰지 마세요.

규칙 예시:
1. 운동 후 → 고단백, 저지방
2. 야식 → 저나트륨, 저지방
3. 바디프로필 준비 → 저탄수화물, 고단백
4. 다이어트 시작 → 저열량, 저지방
5. 한파·추운 날 → 고열량, 고탄수화물
6. 마라톤·경기 전 → 고탄수화물, 고열량
7. 당 떨어졌을 때 → 고당류, 고열량
8. 혈당 관리 → 저당류, 저열량
9. 크림 파스타가 당길 때 → 고지방, 고열량
10. 느끼한 음식이 물렸을 때 → 저지방, 저열량"""
TRAIN_SYSTEM_PROMPT_SHA256 = "06818f0f2ba2c5ac7f05454846c37e9054766184d62cd521b6afe0eab479b556"

# 2026-11-06: 팀원 실험(관계없는 문장 프롬프트 실험)대로 학습 프롬프트 끝에 아래 규칙을 덧붙였다.
# 관계없는 문장이면 모델이 {"nutrients": []}로 답하고, parse_query는 None을 돌려준다.
# 어댑터는 이 규칙 없이 학습했으므로 실제로 쓰는 프롬프트는 학습 때와 다르다.
UNRELATED_RULE = """관계없는 문장 규칙:
사용자 문장이 먹을 것, 식사, 건강, 몸 상태, 상황과 관계없으면(인사, 잡담, 날씨, 감사 인사, 다른 주제 질문 등) 영양소를 고르지 말고 {"nutrients": []} 로만 답하세요."""
SYSTEM_PROMPT = TRAIN_SYSTEM_PROMPT + "\n\n" + UNRELATED_RULE
SYSTEM_PROMPT_SHA256 = "836df788714875a0414050e0e2b54c0331036d1a9de97fc3bef76523212e80d7"

NUTRIENT_KO = {"calories": "열량", "protein": "단백질", "sodium": "나트륨",
               "carbs": "탄수화물", "sugar": "당류", "fat": "지방"}
DIRECTIONS = ("high", "low")


# ---------------------------------------------------------------- 예산 추출 (모델 사용 안 함)
# 2026-11-06: 종호(members/jongho/budget_lab/extract_budget.py, PR #22) 수정안을 반영했다.
# budget은 상한으로만 쓰이므로, 상한이 아닌 금액(넘게·말고·빼고 등)은 쓰지 않고 None을 돌려준다.

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


# ---------------------------------------------------------------- 조건 없는 입력 (모델 사용 안 함)
# 2026-11-06: 모델은 어떤 문장이든 영양소 2개를 고르도록 학습되어, "안녕하세요"에도 영양소를 지어낸다.
# 그래서 인삿말·잡담·일반 요청어만 있는 입력은 모델을 부르지 않고 None을 돌려준다.
# 방법: 문장을 정규화한 뒤 아래 목록의 말을 모두 지우고, 남는 글자가 없을 때만 '조건 없음'으로 본다.
# 길이로는 거르지 않는다. 목록에 없는 말이 한 글자라도 남으면 모델로 보낸다(정상 문장을 막지 않는 쪽을 택함).

# 인삿말·감사·호응·잡담: 이것만으로는 영양 조건이 없다
_CHITCHAT_WORDS = (
    "안녕하세요", "안녕하세여", "안녕하십니까", "안녕", "하이", "헬로우", "헬로", "hello", "hi", "hey",
    "반가워요", "반가워", "반갑습니다", "반가워용", "처음뵙겠습니다",
    "고마워요", "고마워", "고맙습니다", "감사합니다", "감사해요", "감사", "땡큐", "thankyou", "thanks",
    "수고하세요", "수고하셨습니다", "수고많으세요", "수고",
    "뭐해요", "뭐해", "뭐하니", "누구세요", "누구야", "넌누구야", "너누구야",
    "테스트", "test", "여보세요", "ㅎㅇ", "굿모닝", "좋은아침", "좋은하루", "오늘도좋은하루",
    "잘자", "잘가", "바이", "bye", "오케이", "ok", "넵", "네", "응",
    "하하", "히히", "헤헤", "호호",
)
# 일반 요청어: 무엇을 원하는지 없이 추천만 부탁하는 말
_REQUEST_WORDS = (
    "추천해주세요", "추천해줘요", "추천해줘", "추천부탁해요", "추천부탁해", "추천좀", "추천",
    "알려주세요", "알려줘요", "알려줘", "찾아주세요", "찾아줘", "골라주세요", "골라줘",
    "뭐있어요", "뭐있나요", "뭐있어", "뭐먹을까요", "뭐먹을까", "뭐먹지", "뭐마실까", "뭐마시지",
    "먹을거", "먹을것", "마실거", "마실것",
    "부탁드려요", "부탁드립니다", "부탁해요", "부탁해", "해주세요", "해줘",
)
# 덧붙는 말·어미: 위 말과 함께 쓰일 때만 지운다 (조사 '이·가' 같은 한 글자는 낱말을 깎을 수 있어 넣지 않는다)
_FILLER_WORDS = ("저기요", "저기", "혹시", "그냥", "오늘", "님", "좀", "요", "뭐", "거", "것", "도", "음", "어", "아")
# 긴 말부터 지운다. 끝의 [ㅋㅎㅠㅜㅡ]+ 는 웃음·울음 표시(ㅋㅋ, ㅎㅎ, ㅠㅠ)다. 'ㅎㅇ'은 목록에 있어 먼저 지워진다.
_CHITCHAT_RE = re.compile("|".join(sorted(map(re.escape, _CHITCHAT_WORDS + _REQUEST_WORDS + _FILLER_WORDS),
                                          key=len, reverse=True)) + "|[ㅋㅎㅠㅜㅡ]+")
# 남길 글자: 한글 음절, 영문, 숫자, 자음·모음. 공백·문장부호·이모지는 지운다.
_KEEP_CHARS_RE = re.compile(r"[^가-힣a-z0-9ㄱ-ㅣ]")


def _normalize_chitchat(text):
    return _KEEP_CHARS_RE.sub("", text.lower())


def is_no_condition(text):
    """인삿말·잡담·일반 요청어만 있어 영양 조건이 없는 입력이면 True. 다른 말이 조금이라도 남으면 False."""
    if not isinstance(text, str):
        return False
    s = _normalize_chitchat(text)
    while True:  # 지우고 나서 새로 붙은 말("하이뭐먹지")도 지운다
        t = _CHITCHAT_RE.sub("", s)
        if t == s:
            break
        s = t
    return s == ""


def classify_failure(text):
    """parse_query가 모델을 부르기 전에 None을 돌려주는 이유. "empty", "too_long", "no_condition", 해당 없으면 None."""
    if not isinstance(text, str) or not text.strip():
        return "empty"
    if len(text) > MAX_INPUT_CHARS:
        return "too_long"
    if is_no_condition(text):
        return "no_condition"
    return None


# ---------------------------------------------------------------- 모델 응답 변환

UNRELATED_REASON = "관계없는 문장(모델이 빈 목록으로 답함)"


def parse_model_response(raw):
    """모델 응답 문자열 → {"단백질": "high", ...}. 형식이 틀리면 (None, 이유)."""
    decoder = json.JSONDecoder()
    obj = None
    for m in re.finditer(r"\{", raw):
        try:
            candidate, _ = decoder.raw_decode(raw, m.start())
        except ValueError:
            continue
        if isinstance(candidate, dict) and "nutrients" in candidate:
            obj = candidate
            break
    if obj is None:
        return None, "nutrients를 가진 JSON 객체 없음"
    items = obj["nutrients"]
    if items == []:
        return None, UNRELATED_REASON
    if not isinstance(items, list) or len(items) != 2:
        return None, "nutrients가 2개짜리 목록이 아님"
    result = {}
    for item in items:
        if not isinstance(item, dict):
            return None, f"항목이 객체가 아님: {item!r}"
        nutrient, direction = item.get("nutrient"), item.get("direction")
        # 평가 때와 같게 앞뒤 공백과 대소문자는 정규화한다
        nutrient = nutrient.strip().lower() if isinstance(nutrient, str) else nutrient
        direction = direction.strip().lower() if isinstance(direction, str) else direction
        if not isinstance(nutrient, str) or nutrient not in NUTRIENT_KO:
            return None, f"허용되지 않은 성분: {nutrient!r}"
        if direction not in DIRECTIONS:
            return None, f"허용되지 않은 방향: {direction!r}"
        name = NUTRIENT_KO[nutrient]
        if name in result:
            return None, f"성분 중복: {nutrient}"
        result[name] = direction
    return result, None


# ---------------------------------------------------------------- 모델 로딩과 생성

def _post(path, payload, timeout=300):
    request = urllib.request.Request(f"{OLLAMA_URL}{path}", json.dumps(payload).encode("utf-8"),
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def load_model():
    """프롬프트를 확인하고 Ollama 모델을 미리 한 번 불러 둔다. 실패하면 예외를 던진다."""
    train_sha = hashlib.sha256(TRAIN_SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    if train_sha != TRAIN_SYSTEM_PROMPT_SHA256:
        raise RuntimeError(f"학습 프롬프트 sha256 불일치: {train_sha}")
    actual_sha = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    if actual_sha != SYSTEM_PROMPT_SHA256:
        raise RuntimeError(f"시스템 프롬프트 sha256 불일치: {actual_sha}")
    _post("/api/show", {"model": OLLAMA_MODEL}, timeout=30)
    _generate("워밍업")
    logger.info("Ollama 모델 사용: %s", OLLAMA_MODEL)
    return {"backend": "ollama", "model": OLLAMA_MODEL}


def _generate(text):
    """사용자 문장 하나에 대한 모델 응답 문자열 (문장 하나씩, greedy)."""
    body = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": text,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0, "num_predict": MAX_NEW_TOKENS},
    }
    return _post("/api/generate", body)["response"]


def parse_query_with_reason(text):
    """사용자 문장 → (결과, 이유). 성공하면 (dict, None), 실패하면 (None, 이유 코드).

    이유 코드: "empty", "too_long", "no_condition", "unrelated", "invalid_output", "error"
    """
    reason = classify_failure(text)
    if reason is not None:
        if reason == "empty":
            logger.warning("입력이 비어 있어 모델을 부르지 않음")
        elif reason == "too_long":
            logger.warning("입력이 너무 길어 모델을 부르지 않음: %d자 (최대 %d자)", len(text), MAX_INPUT_CHARS)
        else:
            logger.warning("영양 조건이 없는 입력(인삿말·잡담)이라 모델을 부르지 않음: %.50s", text)
        return None, reason
    try:
        raw = _generate(text)
        nutrients, detail = parse_model_response(raw)
        if nutrients is not None:
            return {"budget": extract_budget(text), "nutrients": nutrients}, None
        if detail == UNRELATED_REASON:
            logger.warning("%s: %.50s", detail, text)
            return None, "unrelated"
        logger.warning("모델 응답 검증 실패: %s | 응답: %.200s", detail, raw)
        return None, "invalid_output"
    except Exception:
        logger.exception("parse_query 실행 중 오류")
        return None, "error"


def parse_query(text):
    """사용자 문장 → {"budget": int|None, "nutrients": {성분: 방향, 성분: 방향}}. 실패하면 None (이유는 로그).

    이유가 필요하면 parse_query_with_reason을 쓴다.
    """
    return parse_query_with_reason(text)[0]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('사용법: python -m query_parser "5천원 이하로 운동 후에 먹을 거"', file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    result = parse_query(argv[0])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
