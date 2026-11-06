"""문장을 추천 조건으로 바꾸는 규칙 파서. A.X 4.0 Light를 연결하기 전까지 쓰는 대체품이다.

출력은 slot_eval의 A.X 출력 스키마(prompts/system_v0.txt)와 같은 형식이다.
A.X로 바꿀 때는 parse_request만 교체하면 나머지 코드는 그대로 쓸 수 있다.
"""
import re
from dataclasses import dataclass, field

NUTRIENT_KEYS = ("calories", "carbs", "protein", "fat", "sugar", "sodium")
MAX_CONDITIONS = 3

GOAL_DEFAULTS = {
    "다이어트": [("calories", "low"), ("protein", "high")],
    "근력": [("protein", "high"), ("fat", "low"), ("sugar", "low")],
    "벌크업": [("calories", "high"), ("protein", "high")],
    # 사용자가 확정한 운동 후 라벨(SIT01): 단백질↑ 지방↓ 당↓
    "운동 후": [("protein", "high"), ("fat", "low"), ("sugar", "low")],
}
KOREAN_THOUSANDS = {
    "이천": 2000, "삼천": 3000, "사천": 4000, "오천": 5000,
    "육천": 6000, "칠천": 7000, "팔천": 8000, "구천": 9000,
}
PRE_WORKOUT_WORDS = (
    "운동 전", "운동전", "운동 가기 전", "운동 가기전", "운동가기 전", "운동가기전",
    "운동 하기 전", "운동하기 전", "운동하기전", "운동 시작 전", "운동 시작전", "운동시작 전", "운동시작전",
    "운동 나가기 전", "운동 나가기전", "운동나가기 전", "운동나가기전",
)
NOT_WORKOUT_WORDS = ("운동 안", "운동안", "운동 못", "운동못", "운동화", "운동복", "운동회", "운동장")


@dataclass
class ParseResult:
    slots: dict
    goal: str | None = None
    quick_replies: list[str] = field(default_factory=list)


def parse_budget(text):
    match = re.search(r"(\d+)\s*만\s*(\d+)\s*천\s*원", text)
    if match:
        return int(match[1]) * 10000 + int(match[2]) * 1000
    match = re.search(r"(\d+)\s*만\s*원", text)
    if match:
        return int(match[1]) * 10000
    match = re.search(r"(\d+)\s*천\s*원", text)
    if match:
        return int(match[1]) * 1000
    match = re.search(r"(\d[\d,]{2,})\s*원", text)
    if match:
        return int(match[1].replace(",", ""))
    for word, value in KOREAN_THOUSANDS.items():
        if re.search(word + r"\s*원", text):
            return value
    if re.search(r"(^|[^\d가-힣])만\s*원", text):
        return 10000
    return None


def parse_count(text):
    if re.search(r"(두|2)\s*(개|병|가지)", text):
        return 2
    if re.search(r"(세|3)\s*(개|병|가지)", text):
        return 3
    return None


def find_goal(has):
    if has("벌크", "살 찌", "증량"):
        return "벌크업"
    if has("근육", "근손실", "하체", "등 운동", "웨이트", "헬스", "PT", "피티", "쇠질", "근력"):
        return "근력"
    if has("다이어트", "살 빼", "감량", "다욧", "체중 관리", "유산소"):
        return "다이어트"
    if has("운동") and not has(*PRE_WORKOUT_WORDS, *NOT_WORKOUT_WORDS):
        return "운동 후"
    return None


def find_conditions(has):
    conditions = []

    def add(nutrient, direction):
        if all(existing != nutrient for existing, _ in conditions):
            conditions.append((nutrient, direction))

    if has("땀", "짭짤", "짠 게", "짠거 땡", "더위", "사우나", "단짠"):
        add("sodium", "high")
    if has("붓기", "부었", "부어", "덜 짠", "안 짠", "싱겁", "저염", "회식", "숙취", "라면 많이"):
        add("sodium", "low")
    if has("카보", "시합", *PRE_WORKOUT_WORDS, "밥이 당", "면이 당", "빵이 당", "리피드"):
        add("carbs", "high")
    if has("밥 빼", "탄수 줄", "저탄", "키토", "밀가루", "탄수 적"):
        add("carbs", "low")
    if has("덜 단", "덜 달", "안 단", "제로", "무가당", "저당", "단 거 끊", "단거 끊", "달지 않"):
        add("sugar", "low")
    elif has("달달", "단 게 당", "단거", "디저트", "당 충전", "후식", "기운 없"):
        add("sugar", "high")
    if has("담백", "느끼", "기름기", "튀김 빼", "튀김은 빼", "저지방"):
        add("fat", "low")
    elif has("고소", "바삭", "치즈 듬뿍", "튀김 당", "튀김이 당", "기름진 게 당"):
        add("fat", "high")
    if has("단백질", "근육", "근손실", "하체", "등 운동", "웨이트", "헬스", "PT", "피티", "닭가슴살", "포만", "쇠질", "근력"):
        add("protein", "high")
    if has("가볍게", "저칼로리", "칼로리 낮", "적게", "조금만"):
        add("calories", "low")
    if has("든든", "배고파", "많이 먹", "벌크", "살 찌", "양 많"):
        add("calories", "high")

    goal = find_goal(has)
    for nutrient, direction in GOAL_DEFAULTS.get(goal, []):
        add(nutrient, direction)
    return goal, conditions[:MAX_CONDITIONS]


def parse_request(text, categories):
    """문장과 고른 카테고리를 받아 A.X 스키마 형식의 조건을 돌려준다."""
    normalized = re.sub(r"\s+", " ", text).strip()

    def has(*keywords):
        return any(keyword in normalized for keyword in keywords)

    goal, conditions = find_conditions(has)
    nutrients = dict.fromkeys(NUTRIENT_KEYS)
    nutrients.update(conditions)

    question, quick_replies = None, []
    if not conditions:
        question = "어떤 쪽으로 찾아볼까요? 하나만 골라 주세요."
        quick_replies = ["든든하게", "가볍게", "단백질 많이", "덜 달게"]

    slots = {
        "nutrients": nutrients,
        "constraints": [],
        "budget": parse_budget(normalized),
        "count": parse_count(normalized),
        "price_priority": bool(re.search(r"가성비|가격\s*대비", normalized)),
        "need_clarification": question is not None,
        "clarification_question": question,
        "issue": None,
    }
    return ParseResult(slots=slots, goal=goal if conditions else None, quick_replies=quick_replies)
