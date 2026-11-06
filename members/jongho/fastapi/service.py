"""팀 필터 엔진과 cu_products.db를 화면 형식으로 연결한다. 팀 코드와 DB는 읽기만 한다."""
import os
import sqlite3
import sys
import threading
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "members" / "hayoung" / "finetune_v1" / "code"))

from pickcu.filter_engine import (  # noqa: E402
    NUTRIENT_COLUMNS,
    REDUCE_FROM_CATEGORIES,
    build_combinations,
    rank_key,
    reduce_candidates,
    score_items,
    select_top,
    to_result,
    validate_nutrients,
)
from pickcu.product_search import CATEGORIES, DB_PATH, search_candidates  # noqa: E402

import query_parser  # noqa: E402
import review_store  # noqa: E402
from nlu import NUTRIENT_KEYS, ParseResult, parse_request  # noqa: E402

COLUMN_TO_KOREAN = {column: korean for korean, column in NUTRIENT_COLUMNS.items()}
KOREAN_TO_COLUMN = {korean: column for column, korean in COLUMN_TO_KOREAN.items()}
MODEL_READY = False
_model_lock = threading.Lock()
MIN_BUDGET = 1000  # 이보다 작은 예산은 추천하지 않고 다시 입력하도록 안내한다
NUTRITION_COLUMNS = tuple(COLUMN_TO_KOREAN)
RELAX_BUDGET_RATE = 1.1
# 설계의 "총점 + 0.1 × R"은 0~1 척도 기준이다. 엔진 총점은 0~100이라 같은 비중이 되도록 10을 곱한다.
REVIEW_WEIGHT = 10
SORT_SQL = {
    "default": "p.product_name ASC, p.item_cd ASC",
    "price": "p.price ASC, p.item_cd ASC",
    "protein": "p.protein DESC, p.item_cd ASC",
    "sugar": "p.sugar ASC, p.item_cd ASC",
    "calories": "p.calories ASC, p.item_cd ASC",
    "sodium": "p.sodium ASC, p.item_cd ASC",
}
PRODUCT_COLUMNS = (
    "p.item_cd, p.category, p.product_name, p.price, p.event_type, "
    "p.calories, p.protein, p.sodium, p.carbs, p.sugar, p.fat, p.thumbnail_url AS image_url"
)


def connect_products():
    """상품 DB에 리뷰 DB를 rv로 붙여 읽기 전용으로 연다."""
    connection = sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("ATTACH DATABASE ? AS rv", (review_store.attach_uri(),))
    return connection


def list_categories():
    with closing(connect_products()) as connection:
        counts = dict(connection.execute("SELECT category, COUNT(*) FROM cu_products GROUP BY category").fetchall())
    categories = [{"name": name, "count": counts.get(name, 0)} for name in CATEGORIES]
    return {"categories": categories, "total": sum(counts.values())}


def list_products(category=None, query="", sort="default", promo=None, page=1, size=20):
    where, params = ["1 = 1"], []
    if category:
        where.append("p.category = ?")
        params.append(category)
    if promo:
        where.append("p.event_type = ?")
        params.append(promo)
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("p.product_name LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
    where_sql = " AND ".join(where)
    stats_sql = review_store.STATS_SQL.format(prefix="rv.")
    with closing(connect_products()) as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM cu_products AS p WHERE {where_sql}", params).fetchone()[0]
        rows = connection.execute(
            f"""SELECT {PRODUCT_COLUMNS}, ROUND(s.average, 1) AS avg_rating, COALESCE(s.n_reviews, 0) AS n_reviews
                FROM cu_products AS p LEFT JOIN ({stats_sql}) AS s ON s.barcode = p.item_cd
                WHERE {where_sql} ORDER BY {SORT_SQL[sort]} LIMIT ? OFFSET ?""",
            [*params, size, (page - 1) * size],
        ).fetchall()
    return {"total": total, "page": page, "size": size, "items": [dict(row) for row in rows]}


def lookup_products(barcodes):
    """{바코드: 상품 정보}. 상품 DB에 없는 바코드는 들어 있지 않다."""
    if not barcodes:
        return {}
    marks = ",".join("?" for _ in barcodes)
    with closing(connect_products()) as connection:
        rows = connection.execute(
            f"SELECT {PRODUCT_COLUMNS} FROM cu_products AS p WHERE p.item_cd IN ({marks})", list(barcodes)
        ).fetchall()
    return {row["item_cd"]: dict(row) for row in rows}


def list_reviews_with_products(barcode=None, combo_key=None, session_id=None, limit=20):
    reviews = review_store.list_reviews(barcode, combo_key, session_id, limit)
    products = lookup_products(sorted({code for review in reviews for code in review["barcodes"]}))
    for review in reviews:
        review["items"] = [
            {
                "barcode": code,
                "product_name": products.get(code, {}).get("product_name"),
                "image_url": products.get(code, {}).get("image_url"),
                "category": products.get(code, {}).get("category"),
            }
            for code in review["barcodes"]
        ]
    return reviews


def apply_review_scores(combinations):
    """엔진이 만든 조합의 총점에 리뷰 점수를 더하고 정렬 키를 다시 만든다."""
    scores, default = review_store.review_scores()
    if not scores:
        return combinations
    adjusted = []
    for key, picks, total_score, nutrition_score, price_score, total_price in combinations:
        review_score = sum(scores.get(item["item_cd"], default) for item in picks) / len(picks)
        new_total = total_score + REVIEW_WEIGHT * review_score
        new_key = rank_key(new_total, nutrition_score, total_price, key[3])
        adjusted.append((new_key, picks, new_total, nutrition_score, price_score, total_price))
    return adjusted


def recommend_with_reviews(categories, nutrients, budget=None):
    """팀 엔진 recommend()와 같은 순서로 부품을 호출하고, 순위를 정하기 전에 리뷰 점수만 더한다.

    팀 엔진은 수정하지 않는다. 리뷰가 하나도 없으면 결과는 recommend()와 똑같다.
    """
    validate_nutrients(nutrients)
    candidates = search_candidates(categories, budget=budget)
    scores = {}
    for items in candidates.values():
        scores.update(score_items(items, nutrients))
    if len(candidates) >= REDUCE_FROM_CATEGORIES:
        candidates = {category: reduce_candidates(items, scores) for category, items in candidates.items()}
    use_price = budget is not None and len(candidates) > 1
    combinations = apply_review_scores(build_combinations(candidates, scores, budget, use_price))
    return [to_result(rank, combination, scores) for rank, combination in enumerate(select_top(combinations), 1)]


def to_display(result):
    """화면 형식: 합계와 상품별 별점을 붙이고 thumbnail_url을 image_url로 내보낸다."""
    stats = {row["barcode"]: row for row in review_store.product_stats([item["item_cd"] for item in result["items"]])}
    items = []
    for item in result["items"]:
        shown = {key: value for key, value in item.items() if key != "thumbnail_url"}
        items.append({
            **shown,
            "image_url": item.get("thumbnail_url"),
            "avg_rating": stats[item["item_cd"]]["avg_rating"],
            "n_reviews": stats[item["item_cd"]]["n_reviews"],
        })
    totals = {column: round(sum(item[column] for item in items), 1) for column in NUTRITION_COLUMNS}
    return {**result, "items": items, "totals": totals}


def rerank_by_value(results):
    """엔진에는 가격대비 정렬이 없어서 Top 5 안에서만 영양 점수 ÷ 합계 순서로 다시 놓는다."""
    ordered = sorted(results, key=lambda row: -row["nutrition_score"] / row["total_price"])
    return [{**row, "rank": rank} for rank, row in enumerate(ordered, 1)]


def load_parser_model():
    """PICKCU_PARSER가 ax(기본값)면 A.X를 불러온다. 실패하면 규칙 파서로 동작한다."""
    global MODEL_READY
    if os.environ.get("PICKCU_PARSER", "ax") != "ax":
        return
    try:
        query_parser.load_model()
        MODEL_READY = True
        print("A.X 모델 로딩 완료", flush=True)
    except Exception as error:  # GPU·패키지·어댑터가 없을 때
        print(f"A.X를 불러오지 못해 규칙 파서를 씁니다: {error}", flush=True)


def parse_text(full_text, categories):
    """(해석 결과, parser, 영양소를 찾았는지). A.X가 None을 내면 영양소를 찾지 못한 것으로 본다.

    모델을 쓸 수 없을 때(MODEL_READY가 False)만 규칙 파서 결과를 쓴다.
    """
    rule = parse_request(full_text, categories)
    if not MODEL_READY:
        return rule, "rule", True
    with _model_lock:  # GPU 하나에서 생성이 겹치지 않게 한다
        query = query_parser.parse_query(full_text)
    if query is None:
        slots = {
            **rule.slots,
            "nutrients": dict.fromkeys(NUTRIENT_KEYS),
            "need_clarification": False,
            "clarification_question": None,
        }
        return ParseResult(slots=slots, goal=None, quick_replies=[]), "ax", False
    nutrients = dict.fromkeys(NUTRIENT_KEYS)
    nutrients.update({KOREAN_TO_COLUMN[name]: direction for name, direction in query["nutrients"].items()})
    slots = {
        **rule.slots,
        "nutrients": nutrients,
        "budget": query["budget"],
        "need_clarification": False,
        "clarification_question": None,
    }
    return ParseResult(slots=slots, goal=None, quick_replies=[]), "ax", True


def build_response(status, parsed, goal=None, quick_replies=None, results=None, relaxed=None, notice=None, parser="rule"):
    results = results or []
    return {
        "status": status,
        "parsed": parsed,
        "goal": goal,
        "quick_replies": quick_replies or [],
        "mode": ("조합" if len(results[0]["items"]) > 1 else "단품") if results else None,
        "relaxed": relaxed,
        "notice": notice,
        "results": results,
        "source": "db",
        "parser": parser,
    }


def recommend_flow(text, categories, pending_text=None):
    full_text = f"{pending_text} {text}" if pending_text else text
    parsed, parser, found = parse_text(full_text, categories)
    slots = parsed.slots
    if not found:
        return build_response("no_nutrient", slots, parser=parser)
    if slots["budget"] is not None and slots["budget"] < MIN_BUDGET:
        return build_response("budget_too_low", slots, parser=parser)
    if slots["need_clarification"]:
        return build_response("ask", slots, quick_replies=parsed.quick_replies, parser=parser)

    nutrients = {COLUMN_TO_KOREAN[key]: value for key, value in slots["nutrients"].items() if value}
    budget = slots["budget"]
    results = recommend_with_reviews(categories, nutrients, budget=budget)

    relaxed = None
    if not results and budget:
        used_budget = int(budget * RELAX_BUDGET_RATE)
        results = recommend_with_reviews(categories, nutrients, budget=used_budget)
        if results:
            relaxed = {
                "message": f"예산 안에서는 찾지 못해 {used_budget:,}원까지 넓혀서 찾았어요.",
                "original_budget": budget,
                "used_budget": used_budget,
            }
    if not results:
        return build_response("empty", slots, goal=parsed.goal, parser=parser)

    if slots["price_priority"]:
        results = rerank_by_value(results)
    notice = None
    if slots["count"] and slots["count"] != len(categories):
        notice = f"지금 추천은 고른 카테고리마다 1개씩 담아 {len(categories)}개 기준으로 찾아요."
    return build_response(
        "ok", slots, goal=parsed.goal,
        results=[to_display(row) for row in results], relaxed=relaxed, notice=notice, parser=parser,
    )
