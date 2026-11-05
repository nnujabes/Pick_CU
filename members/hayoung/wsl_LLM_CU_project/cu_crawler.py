"""
CU 편의점 전체상품 크롤러
- 출처: https://cu.bgfretail.com/product/product.do (전체 상품)
- 수집 컬럼: display_name, price, event_type ('1+1' | '2+1' | 'NONE')
- 기본 제외: 생활용품 카테고리(70), NEW 태그가 붙은 신상품

사용법:
    pip install requests beautifulsoup4
    python cu_crawler.py                  # cu_products.csv 저장
    python cu_crawler.py --db cvs.db      # SQLite 테이블(cu_products)에도 저장
"""

import argparse
import csv
import sqlite3
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://cu.bgfretail.com"
AJAX_URL = f"{BASE_URL}/product/productAjax.do"

# searchMainCategory 코드
CATEGORIES = {
    10: "간편식사",
    20: "즉석조리",
    30: "과자류",
    40: "아이스크림",
    50: "식품",
    60: "음료",
    70: "생활용품",
}
EXCLUDED_CATEGORIES = {70}  # 생활용품

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE_URL}/product/product.do?category=product&depth2=4",
}


def _parse_event(li) -> str:
    """badge > span.plus1 → '1+1', span.plus2 → '2+1', 없으면 'NONE'"""
    badge = li.select_one(".badge span")
    if badge is None:
        return "NONE"
    classes = badge.get("class", [])
    if "plus1" in classes:
        return "1+1"
    if "plus2" in classes:
        return "2+1"
    return "NONE"


def fetch_page(session: requests.Session, category: int, page: int) -> list[dict]:
    """카테고리 한 페이지(보통 40개)를 가져와 파싱한다."""
    data = {
        "pageIndex": page,
        "searchMainCategory": category,
        "searchSubCategory": "",
        "listType": 1,
        "searchCondition": "setA",
        "searchUseYn": "",
        "gdIdx": 0,
        "codeParent": category,
        "user_id": "",
        "search1": "",
        "search2": "",
        "searchKeyword": "",
    }
    resp = session.post(AJAX_URL, data=data, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    for li in soup.select("li.prod_list"):
        name_el = li.select_one(".name p")
        price_el = li.select_one(".price strong")
        if not name_el or not price_el:
            continue
        onclick = li.select_one(".name").get("onclick", "")
        prod_id = "".join(ch for ch in onclick if ch.isdigit())
        items.append({
            "id": prod_id,  # 중복 제거용 CU 내부 상품 ID
            "category": category,
            "display_name": name_el.get_text(strip=True),
            "price": int("".join(ch for ch in price_el.get_text() if ch.isdigit())),
            "event_type": _parse_event(li),
            "is_new": li.select_one(".tag .new") is not None,
        })
    return items


def crawl_cu(exclude_new: bool = True,
             exclude_categories: set[int] = EXCLUDED_CATEGORIES,
             delay: float = 0.3,
             max_pages: int = 300) -> list[dict]:
    """
    CU 전체상품을 카테고리별로 끝까지 수집한다.
    더 이상 새 상품 ID가 나오지 않으면 다음 카테고리로 넘어간다.
    반환: [{'display_name', 'price', 'event_type', ...}, ...]
    """
    results = []
    with requests.Session() as session:
        for cat, cat_name in CATEGORIES.items():
            if cat in exclude_categories:
                continue
            seen = set()
            for page in range(1, max_pages + 1):
                items = fetch_page(session, cat, page)
                fresh = [it for it in items if it["id"] not in seen]
                if not fresh:
                    break
                seen.update(it["id"] for it in fresh)
                results.extend(fresh)
                time.sleep(delay)
            print(f"[{cat_name}] {len(seen)}개 수집")

    if exclude_new:
        results = [r for r in results if not r["is_new"]]
    return results


def save_csv(rows: list[dict], path: str = "cu_products.csv") -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["display_name", "price", "event_type"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def save_sqlite(rows: list[dict], path: str = "cvs.db") -> None:
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS cu_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            event_type TEXT DEFAULT 'NONE'
        )
    """)
    con.execute("DELETE FROM cu_products")
    con.executemany(
        "INSERT INTO cu_products (display_name, price, event_type) VALUES (?, ?, ?)",
        [(r["display_name"], r["price"], r["event_type"]) for r in rows],
    )
    con.commit()
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cu_products.csv")
    ap.add_argument("--db", default=None, help="SQLite 경로 (지정 시 함께 저장)")
    ap.add_argument("--include-new", action="store_true", help="신상품도 포함")
    args = ap.parse_args()

    rows = crawl_cu(exclude_new=not args.include_new)
    save_csv(rows, args.out)
    if args.db:
        save_sqlite(rows, args.db)

    from collections import Counter
    print(f"총 {len(rows)}개 저장 →", args.out)
    print(Counter(r["event_type"] for r in rows))
