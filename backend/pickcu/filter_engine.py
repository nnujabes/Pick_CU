"""검색한 후보 상품에 점수를 매겨 Top 5 추천을 만든다.

점수 규칙:
    총점 = 0.7 × 영양 점수 + 0.3 × 가격 점수
    - 영양 점수: 같은 카테고리 후보 안의 백분위. high는 그대로, low는 뒤집고, 조건이 여러 개면 평균한다.
    - 가격 점수: 합계 ÷ 예산 × 100. 예산에 가까울수록 높다.
    - 금액이 없거나 카테고리가 1개면 가격 점수 없이 영양 점수만 쓴다.
    - 합계는 예산을 넘을 수 없고, Top 5 안에서 같은 상품은 한 번만 쓴다.
    - 행사(1+1, 2+1)는 계산하지 않고 화면 표시용으로 event_type만 넘긴다.

사용 예:
    from pickcu.filter_engine import recommend

    results = recommend(["간편식사", "음료"], {"단백질": "high", "당류": "low"}, budget=10000)
    if not results:
        ...  # 조건을 다시 입력하라고 재질문한다
"""
import itertools
from bisect import bisect_left, bisect_right
from operator import itemgetter

from .product_search import DB_PATH, search_candidates

NUTRIENT_COLUMNS = {
    "열량": "calories",
    "단백질": "protein",
    "나트륨": "sodium",
    "탄수화물": "carbs",
    "당류": "sugar",
    "지방": "fat",
}
DIRECTIONS = ("high", "low")
NUTRITION_WEIGHT = 0.7
PRICE_WEIGHT = 0.3
TOP_K = 5

# 카테고리 3개는 조합이 최대 약 5,100만 개라서 카테고리별로 후보를 줄인 뒤 조합한다.
# 저렴한 상품을 함께 남겨야 낮은 예산에서도 예산 안의 조합이 나온다.
REDUCE_FROM_CATEGORIES = 3
TOP_BY_NUTRITION = 20
TOP_BY_LOW_PRICE = 10


def validate_nutrients(nutrients):
    """영양소 조건은 필수다. 비어 있으면 호출하는 쪽에서 재질문해야 한다."""
    if not isinstance(nutrients, dict):
        raise TypeError("nutrients는 딕셔너리여야 합니다.")
    if not nutrients:
        raise ValueError("영양소 조건이 없습니다. 사용자에게 다시 질문해야 합니다.")
    unknown = [name for name in nutrients if name not in NUTRIENT_COLUMNS]
    if unknown:
        raise ValueError(f"없는 영양소입니다: {unknown}")
    invalid = {name: value for name, value in nutrients.items() if value not in DIRECTIONS}
    if invalid:
        raise ValueError(f"영양소 조건은 high 또는 low여야 합니다: {invalid}")


def score_items(items, nutrients):
    """{item_cd: 영양 점수}를 돌려준다. 같은 값은 중간 순위로 계산한다."""
    columns = [(NUTRIENT_COLUMNS[name], direction) for name, direction in nutrients.items()]
    sorted_values = {column: sorted(item[column] for item in items) for column, _ in columns}
    scores = {}
    for item in items:
        total = 0.0
        for column, direction in columns:
            values = sorted_values[column]
            value = item[column]
            percentile = (bisect_left(values, value) + bisect_right(values, value)) / 2 / len(values) * 100
            total += percentile if direction == "high" else 100 - percentile
        scores[item["item_cd"]] = total / len(columns)
    return scores


def reduce_candidates(items, scores):
    """영양 점수 상위 상품과, 나머지 중 저렴한 상품만 남긴다."""
    by_score = sorted(items, key=lambda item: (-scores[item["item_cd"]], item["price"], item["item_cd"]))
    cheapest = sorted(by_score[TOP_BY_NUTRITION:], key=lambda item: (item["price"], item["item_cd"]))
    return by_score[:TOP_BY_NUTRITION] + cheapest[:TOP_BY_LOW_PRICE]


def rank_key(total_score, nutrition_score, total_price, item_cds):
    """총점 → 영양 점수 → 낮은 합계 → 바코드 순서. 소수 오차가 동점을 깨지 않게 반올림한다."""
    return (-round(total_score, 6), -round(nutrition_score, 6), total_price, item_cds)


def build_combinations(candidates, scores, budget, use_price):
    """예산 안의 조합을 (정렬 키, 상품들, 총점, 영양 점수, 가격 점수, 합계)로 돌려준다."""
    combinations = []
    for picks in itertools.product(*candidates.values()):
        total_price = sum(item["price"] for item in picks)
        if budget is not None and total_price > budget:
            continue
        nutrition_score = sum(scores[item["item_cd"]] for item in picks) / len(picks)
        if use_price:
            price_score = total_price / budget * 100
            total_score = NUTRITION_WEIGHT * nutrition_score + PRICE_WEIGHT * price_score
        else:
            price_score = None
            total_score = nutrition_score
        item_cds = tuple(item["item_cd"] for item in picks)
        key = rank_key(total_score, nutrition_score, total_price, item_cds)
        combinations.append((key, picks, total_score, nutrition_score, price_score, total_price))
    return combinations


def select_top(combinations, k=TOP_K):
    """점수 순서로 보면서 이미 쓴 상품이 들어간 조합은 건너뛴다."""
    selected = []
    used = set()
    for combination in sorted(combinations, key=itemgetter(0)):
        item_cds = combination[0][3]
        if used.intersection(item_cds):
            continue
        selected.append(combination)
        used.update(item_cds)
        if len(selected) == k:
            break
    return selected


def to_result(rank, combination, scores):
    _, picks, total_score, nutrition_score, price_score, total_price = combination
    return {
        "rank": rank,
        "total_score": round(total_score, 1),
        "nutrition_score": round(nutrition_score, 1),
        "price_score": None if price_score is None else round(price_score, 1),
        "total_price": total_price,
        "items": [{**item, "nutrition_score": round(scores[item["item_cd"]], 1)} for item in picks],
    }


def recommend(categories, nutrients, budget=None, db_path=DB_PATH):
    """Top 5 추천을 돌려준다.

    Args:
        categories: 화면에서 고른 카테고리 1~3개. 예: ["간편식사", "음료"]
        nutrients: 자연어에서 추출한 조건. 예: {"단백질": "high", "당류": "low"}
        budget: 자연어에서 추출한 예산(원). 없으면 None이다.
        db_path: DB 파일 경로.

    Returns:
        순위별 추천 리스트. 카테고리마다 상품 1개씩 조합한다. 5개보다 적을 수 있고,
        조건에 맞는 조합이 없으면 빈 리스트다(호출하는 쪽에서 재질문한다).

    Raises:
        TypeError, ValueError: 입력 값이 잘못되었거나 영양소 조건이 없는 경우
        FileNotFoundError: DB 파일이 없는 경우
    """
    validate_nutrients(nutrients)
    candidates = search_candidates(categories, budget=budget, db_path=db_path)

    scores = {}
    for items in candidates.values():
        scores.update(score_items(items, nutrients))
    if len(candidates) >= REDUCE_FROM_CATEGORIES:
        candidates = {category: reduce_candidates(items, scores) for category, items in candidates.items()}

    use_price = budget is not None and len(candidates) > 1
    combinations = build_combinations(candidates, scores, budget, use_price)
    return [to_result(rank, combination, scores) for rank, combination in enumerate(select_top(combinations), 1)]
