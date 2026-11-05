"""사용자 문장 → DB 조회용 조건 JSON 변환 (추론 전용).

    parse_query("5천원 이하로 운동 후에 먹을 거")
    → {"budget": 5000, "nutrients": {"단백질": "high", "지방": "low"}}

- 영양소 2개와 방향은 파인튜닝한 A.X-4.0-Light 어댑터가, 예산은 일반 코드(extract_budget)가 뽑는다.
- 모델에는 시스템 프롬프트와 사용자 문장만 넣는다.
- 어댑터 경로: load_model(경로) > 환경변수 QUERY_PARSER_ADAPTER > DEFAULT_ADAPTER 순서로 정한다.

CLI (ft_ax_v1/code 에서 실행):
    python -m query_parser "5천원 이하로 운동 후에 먹을 거"
"""
import gc
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time

logger = logging.getLogger(__name__)

MODEL_ID = "skt/A.X-4.0-Light"
MODEL_REVISION = "ba21c20ea1b31ded1ec3e2fb432335077dc4be98"
ADAPTER_ENV = "QUERY_PARSER_ADAPTER"
DEFAULT_ADAPTER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "adapter", "best")
MAX_NEW_TOKENS = 128
MAX_INPUT_CHARS = 300  # 이보다 긴 입력은 모델을 부르지 않고 None

# ft_data 학습용 프롬프트와 글자까지 같아야 한다. load_model이 sha256으로 확인한다.
SYSTEM_PROMPT = """당신은 편의점 영양 추천 도우미입니다. 사용자 문장을 보고 필요한 영양소 2개와 방향(높음/낮음)을 JSON으로만 답하세요.

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
SYSTEM_PROMPT_SHA256 = "06818f0f2ba2c5ac7f05454846c37e9054766184d62cd521b6afe0eab479b556"

NUTRIENT_KO = {"calories": "열량", "protein": "단백질", "sodium": "나트륨",
               "carbs": "탄수화물", "sugar": "당류", "fat": "지방"}
DIRECTIONS = ("high", "low")


# ---------------------------------------------------------------- 예산 추출 (모델 사용 안 함)

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


# ---------------------------------------------------------------- 모델 응답 변환

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

_lock = threading.Lock()
_cache = None  # {"model", "tokenizer", "pad_id", "adapter_path"}


def load_model(adapter_path=None):
    """원본 모델(4bit NF4, bf16 계산) + 어댑터를 한 번만 불러 캐시한다. 실패하면 예외를 던진다.

    adapter_path가 None이면 이미 불러온 모델을 그대로 쓰고, 없으면 환경변수나 기본 경로로 불러온다.
    다른 경로로 바꾸려면 unload_model()을 먼저 호출한다.
    """
    global _cache
    with _lock:
        if _cache is not None:
            if adapter_path is None or os.path.abspath(adapter_path) == _cache["adapter_path"]:
                return _cache
            raise ValueError(f"이미 다른 어댑터를 불러옴: {_cache['adapter_path']} (unload_model() 먼저 호출)")

        actual_sha = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
        if actual_sha != SYSTEM_PROMPT_SHA256:
            raise RuntimeError(f"시스템 프롬프트 sha256 불일치: {actual_sha}")
        path = os.path.abspath(adapter_path or os.environ.get(ADAPTER_ENV) or DEFAULT_ADAPTER)
        if not os.path.isfile(os.path.join(path, "adapter_config.json")):
            raise FileNotFoundError(f"어댑터를 찾을 수 없음: {path}")

        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU가 없음 (4bit 로딩에 필요)")
        t0 = time.time()
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                                 bnb_4bit_compute_dtype=torch.bfloat16)
        base = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=MODEL_REVISION, quantization_config=bnb,
                                                    dtype=torch.bfloat16, device_map="cuda")
        model = PeftModel.from_pretrained(base, path)
        model.eval()
        model.config.use_cache = True
        pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
        _cache = {"model": model, "tokenizer": tokenizer, "pad_id": pad_id, "adapter_path": path}
        logger.info("모델 로딩 완료: %s (%.1f초)", path, time.time() - t0)
        return _cache


def unload_model():
    """캐시한 모델을 내리고 GPU 메모리를 정리한다."""
    global _cache
    with _lock:
        _cache = None
    gc.collect()
    _empty_gpu_cache()


def _empty_gpu_cache():
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


def _generate(text):
    """사용자 문장 하나에 대한 모델 응답 문자열 (문장 하나씩, greedy)."""
    import torch

    bundle = load_model()
    tokenizer = bundle["tokenizer"]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]
    enc = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt",
                                        return_dict=True).to("cuda")
    with torch.no_grad():
        out = bundle["model"].generate(**enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                                       pad_token_id=bundle["pad_id"])
    return tokenizer.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)


def parse_query(text):
    """사용자 문장 → {"budget": int|None, "nutrients": {성분: 방향, 성분: 방향}}. 실패하면 None (이유는 로그)."""
    if not isinstance(text, str) or not text.strip():
        logger.warning("입력이 비어 있어 모델을 부르지 않음")
        return None
    if len(text) > MAX_INPUT_CHARS:
        logger.warning("입력이 너무 길어 모델을 부르지 않음: %d자 (최대 %d자)", len(text), MAX_INPUT_CHARS)
        return None
    try:
        raw = _generate(text)
        nutrients, reason = parse_model_response(raw)
        if nutrients is not None:
            return {"budget": extract_budget(text), "nutrients": nutrients}
        logger.warning("모델 응답 검증 실패: %s | 응답: %.200s", reason, raw)
    except Exception:
        logger.exception("parse_query 실행 중 오류")
        _empty_gpu_cache()  # GPU 메모리 부족 뒤에도 다음 호출이 돌 수 있게 한다
    return None


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
