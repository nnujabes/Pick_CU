"""카테고리별 products.csv를 읽어 SQLite 상품 DB(cu_products)를 만든다.

영양소 6개가 모두 있는 상품만 넣는다. 영양소 값은 라벨에 적힌 값이며 기준량은 구분하지 않는다.
실행할 때마다 cu_products 테이블을 새로 만든다. products.csv는 읽기만 한다.
exclude_items.csv에 적은 상품은 DB에 넣되 exclude_reason에 이유를 적어 추천 검색에서 뺀다.

사용법:
    python build_cu_products_db.py
    python build_cu_products_db.py --db 저장할/경로/cu_products.db
"""
import argparse
import csv
import sqlite3
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CATEGORIES_DIR = DATA_DIR / "csv"
DEFAULT_DB_PATH = DATA_DIR / "cu_products.db"
EXCLUDE_PATH = DATA_DIR / "exclude_items.csv"

NUTRIENT_COLUMNS = ["calories", "protein", "sodium", "carbs", "sugar", "fat"]
NO_EVENT = "NONE"

CREATE_SQL = """
DROP TABLE IF EXISTS cu_products;

CREATE TABLE cu_products (
    item_cd TEXT PRIMARY KEY,               -- 바코드 (상품 ID)
    category TEXT NOT NULL,                 -- '간편식사' 등
    product_name TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price > 0),
    event_type TEXT NOT NULL DEFAULT 'NONE'
        CHECK (event_type IN ('NONE', '1+1', '2+1')),

    calories REAL NOT NULL CHECK (calories >= 0),  -- kcal
    protein  REAL NOT NULL CHECK (protein >= 0),   -- g
    sodium   REAL NOT NULL CHECK (sodium >= 0),    -- mg
    carbs    REAL NOT NULL CHECK (carbs >= 0),     -- g
    sugar    REAL NOT NULL CHECK (sugar >= 0),     -- g
    fat      REAL NOT NULL CHECK (fat >= 0),       -- g

    thumbnail_url TEXT,                     -- 상품 목록 이미지 URL
    exclude_reason TEXT                     -- 추천 제외 이유. NULL이면 추천 대상
);

CREATE INDEX idx_category_price ON cu_products (category, price);
"""

INSERT_SQL = """
INSERT INTO cu_products (
    item_cd, category, product_name, price, event_type,
    calories, protein, sodium, carbs, sugar, fat, thumbnail_url, exclude_reason
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def has_all_nutrients(row):
    """값 0은 정상 값이므로 빈 문자열인지만 확인한다."""
    return all(row[column].strip() != "" for column in NUTRIENT_COLUMNS)


def to_record(row):
    return (
        row["item_cd"].strip(),
        row["category_name"].strip(),
        row["product_name"].strip(),
        int(row["price"]),
        row["event"].strip() or NO_EVENT,
        *[float(row[column]) for column in NUTRIENT_COLUMNS],
        row["list_image_url"].strip() or None,
    )


def load_records(categories_dir):
    """상품을 바코드 기준으로 모은다. 같은 바코드가 있으면 행사 정보가 있는 행을 남긴다."""
    csv_paths = sorted(categories_dir.glob("*/products.csv"))
    if not csv_paths:
        raise SystemExit(f"products.csv를 찾지 못했습니다: {categories_dir}")

    records = {}
    total_rows = complete_rows = 0
    for csv_path in csv_paths:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            missing = set(NUTRIENT_COLUMNS) - set(reader.fieldnames or [])
            if missing:
                raise SystemExit(f"영양소 컬럼이 없습니다: {csv_path} {sorted(missing)}")

            for row in reader:
                total_rows += 1
                if not has_all_nutrients(row):
                    continue
                complete_rows += 1
                record = to_record(row)
                item_cd, event_type = record[0], record[4]
                if item_cd not in records or (records[item_cd][4] == NO_EVENT and event_type != NO_EVENT):
                    records[item_cd] = record

    print(f"읽은 행 {total_rows}, 영양소 6개가 모두 있는 행 {complete_rows}, 중복 제거 후 상품 {len(records)}")
    return list(records.values())


def load_exclusions(path):
    """{바코드: 제외 이유}를 돌려준다. 바코드가 겹치거나 이유가 비어 있으면 멈춘다."""
    exclusions = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            item_cd, reason = row["item_cd"].strip(), row["reason"].strip()
            if not reason or item_cd in exclusions:
                raise SystemExit(f"제외 목록 오류(이유 없음 또는 중복): {row}")
            exclusions[item_cd] = reason
    return exclusions


def apply_exclusions(records, exclusions):
    """상품마다 제외 이유를 붙인다. 목록의 바코드가 DB에 없으면 멈춘다."""
    missing = set(exclusions) - {record[0] for record in records}
    if missing:
        raise SystemExit(f"제외 목록의 바코드가 상품에 없습니다: {sorted(missing)}")
    return [(*record, exclusions.get(record[0])) for record in records]


def build_database(db_path, records):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(CREATE_SQL)
        with connection:
            connection.executemany(INSERT_SQL, records)
    finally:
        connection.close()


def print_summary(db_path):
    connection = sqlite3.connect(db_path)
    try:
        total = connection.execute("SELECT COUNT(*) FROM cu_products").fetchone()[0]
        categories = connection.execute("SELECT category, COUNT(*) FROM cu_products GROUP BY category").fetchall()
        events = connection.execute("SELECT event_type, COUNT(*) FROM cu_products GROUP BY event_type").fetchall()
        excluded = connection.execute(
            "SELECT exclude_reason, COUNT(*) FROM cu_products WHERE exclude_reason IS NOT NULL GROUP BY exclude_reason"
        ).fetchall()
    finally:
        connection.close()
    print(f"저장 완료: {db_path} ({total}개)")
    print("카테고리별:", dict(categories))
    print("행사별:", dict(events))
    print("추천 제외:", dict(excluded))


def main():
    parser = argparse.ArgumentParser(description="products.csv로 cu_products SQLite DB를 만든다.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help=f"DB 파일 경로 (기본값: {DEFAULT_DB_PATH})")
    args = parser.parse_args()

    records = apply_exclusions(load_records(CATEGORIES_DIR), load_exclusions(EXCLUDE_PATH))
    build_database(args.db, records)
    print_summary(args.db)


if __name__ == "__main__":
    main()
