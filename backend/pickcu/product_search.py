"""cu_products.db에서 추천 후보 상품을 검색한다.

영양소 high/low는 쿼리에 넣지 않는다. 순위 계산은 다음 단계의 필터 엔진이 맡는다.
소스·양념·조미료처럼 추천에서 뺀 상품(exclude_reason 값이 있는 상품)은 검색하지 않는다.

사용 예:
    from pickcu.product_search import search_candidates

    candidates = search_candidates(["간편식사", "음료"], budget=10000)
    candidates["음료"][0]["product_name"]
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "cu_products.db"
CATEGORIES = ("간편식사", "즉석조리", "과자류", "아이스크림", "식품", "음료")
MAX_CATEGORIES = 3

SELECT_SQL = """
SELECT item_cd, category, product_name, price, event_type,
       calories, protein, sodium, carbs, sugar, fat, thumbnail_url
FROM cu_products
WHERE category = ?
  AND exclude_reason IS NULL
"""
PRICE_SQL = "  AND price <= ?\n"
ORDER_SQL = "ORDER BY price, item_cd"


def validate(categories, budget):
    if not isinstance(categories, (list, tuple)):
        raise TypeError("categories는 리스트여야 합니다.")
    if not 1 <= len(categories) <= MAX_CATEGORIES:
        raise ValueError(f"카테고리는 1~{MAX_CATEGORIES}개를 선택해야 합니다: {categories}")
    if len(set(categories)) != len(categories):
        raise ValueError(f"카테고리가 중복되었습니다: {categories}")
    unknown = [category for category in categories if category not in CATEGORIES]
    if unknown:
        raise ValueError(f"없는 카테고리입니다: {unknown}")
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0):
        raise ValueError(f"budget은 양의 정수 또는 None이어야 합니다: {budget}")


def search_candidates(categories, budget=None, db_path=DB_PATH):
    """카테고리별 후보 상품을 가격 오름차순으로 돌려준다.

    Args:
        categories: 화면에서 고른 카테고리 1~3개. 예: ["간편식사", "음료"]
        budget: 자연어에서 추출한 예산(원). 이 금액 이하만 검색하며, None이면 가격 제한이 없다.
        db_path: DB 파일 경로.

    Returns:
        {"간편식사": [상품 dict, ...], "음료": [...]}. 후보가 없는 카테고리는 빈 리스트다.

    Raises:
        TypeError, ValueError: 입력 값이 잘못된 경우
        FileNotFoundError: DB 파일이 없는 경우
    """
    validate(categories, budget)
    db_path = Path(db_path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"DB 파일이 없습니다: {db_path}")

    sql = SELECT_SQL + (PRICE_SQL if budget is not None else "") + ORDER_SQL
    connection = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        candidates = {}
        for category in categories:
            params = (category,) if budget is None else (category, budget)
            candidates[category] = [dict(row) for row in connection.execute(sql, params)]
    finally:
        connection.close()
    return candidates
