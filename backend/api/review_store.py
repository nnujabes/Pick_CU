"""리뷰를 상품 DB와 분리된 backend/data/reviews.db에 저장한다.

상품과는 바코드로만 연결한다. 그래서 상품 DB를 다시 만들어도, 단종으로 상품이 사라져도 리뷰는 남는다.
"""
import json
import sqlite3
from contextlib import closing
from pathlib import Path

REVIEW_DB = Path(__file__).resolve().parents[1] / "data" / "reviews.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    combo_key TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT CHECK (length(comment) <= 200),
    query_text TEXT,
    parsed_json TEXT,
    session_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS review_items (
    review_id INTEGER REFERENCES reviews(id) ON DELETE CASCADE,
    barcode TEXT NOT NULL,
    PRIMARY KEY (review_id, barcode)
);
CREATE INDEX IF NOT EXISTS idx_review_items_barcode ON review_items (barcode);
CREATE UNIQUE INDEX IF NOT EXISTS idx_review_session_combo ON reviews (session_id, combo_key);
"""
# 상품 조회에서 ATTACH한 rv 스키마와 함께 쓰는 집계 쿼리
STATS_SQL = """
SELECT item.barcode AS barcode, AVG(review.rating) AS average, COUNT(*) AS n_reviews
FROM {prefix}review_items AS item
JOIN {prefix}reviews AS review ON review.id = item.review_id
GROUP BY item.barcode
"""


def init_db():
    """파일과 테이블이 없으면 만든다."""
    REVIEW_DB.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(REVIEW_DB)) as connection, connection:
        connection.executescript(SCHEMA)


def connect():
    init_db()
    connection = sqlite3.connect(REVIEW_DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def attach_uri():
    """상품 DB 연결에 읽기 전용으로 붙일 주소."""
    init_db()
    return f"{REVIEW_DB.resolve().as_uri()}?mode=ro"


def make_combo_key(barcodes):
    return "|".join(sorted(set(barcodes)))


def product_stats(barcodes):
    marks = ",".join("?" for _ in barcodes)
    sql = f"SELECT * FROM ({STATS_SQL.format(prefix='')}) WHERE barcode IN ({marks})"
    with closing(connect()) as connection:
        found = {row["barcode"]: row for row in connection.execute(sql, list(barcodes))}
    return [
        {
            "barcode": barcode,
            "avg_rating": round(found[barcode]["average"], 1) if barcode in found else None,
            "n_reviews": found[barcode]["n_reviews"] if barcode in found else 0,
        }
        for barcode in dict.fromkeys(barcodes)
    ]


def save_review(barcodes, rating, comment, query_text, parsed_json, session_id):
    """같은 session_id + combo_key가 있으면 새로 만들지 않고 고친다."""
    parsed_text = None if parsed_json is None else json.dumps(parsed_json, ensure_ascii=False)
    unique = sorted(set(barcodes))
    with closing(connect()) as connection, connection:
        review_id = connection.execute(
            """INSERT INTO reviews (combo_key, rating, comment, query_text, parsed_json, session_id)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (session_id, combo_key) DO UPDATE SET
                   rating = excluded.rating,
                   comment = excluded.comment,
                   query_text = excluded.query_text,
                   parsed_json = excluded.parsed_json,
                   updated_at = CURRENT_TIMESTAMP
               RETURNING id""",
            (make_combo_key(unique), rating, comment, query_text, parsed_text, session_id),
        ).fetchone()[0]
        connection.executemany(
            "INSERT OR IGNORE INTO review_items (review_id, barcode) VALUES (?, ?)",
            [(review_id, barcode) for barcode in unique],
        )
    return review_id


def list_reviews(barcode=None, combo_key=None, session_id=None, limit=20):
    where, params = [], []
    if barcode:
        where.append("id IN (SELECT review_id FROM review_items WHERE barcode = ?)")
        params.append(barcode)
    if combo_key:
        where.append("combo_key = ?")
        params.append(combo_key)
    if session_id:
        where.append("session_id = ?")
        params.append(session_id)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with closing(connect()) as connection:
        rows = connection.execute(
            f"""SELECT id, combo_key, rating, comment, query_text, created_at, updated_at
                FROM reviews {where_sql}
                ORDER BY COALESCE(updated_at, created_at) DESC, id DESC LIMIT ?""",
            [*params, limit],
        ).fetchall()
    return [
        {**dict(row), "barcodes": row["combo_key"].split("|")}
        for row in rows
    ]


def review_scores():
    """추천 점수에 쓸 리뷰 점수 R. ({barcode: R}, 리뷰 없는 상품의 R)을 돌려준다.

    R = (n × 평균 + 5 × 전체평균) ÷ (n + 5) ÷ 5. 리뷰가 하나도 없으면 ({}, 0.0)이다.
    """
    prior = 5
    with closing(connect()) as connection:
        overall = connection.execute("SELECT AVG(rating) FROM reviews").fetchone()[0]
        if overall is None:
            return {}, 0.0
        rows = connection.execute(STATS_SQL.format(prefix="")).fetchall()
    scores = {
        row["barcode"]: (row["n_reviews"] * row["average"] + prior * overall) / (row["n_reviews"] + prior) / 5
        for row in rows
    }
    return scores, overall / 5
