"""
CU 상품 목록 및 영양정보 이미지 수집 프로그램 (가격 및 행사 정보 포함)

처음 실행:
    홈페이지 상품 목록 수집 → products.csv 생성 → 이미지 다운로드

재실행:
    저장된 목록과 진행 기록을 읽어 미완료 작업 재개

필요 패키지:
    requests
    beautifulsoup4
"""

import argparse
import csv
import json
import re
import shutil
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# 기본 설정
# ============================================================

WEB = "https://cu.bgfretail.com"
POCKET = "https://www.pocketcu.co.kr"

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Mobile/15E148;BGFCU"
)

CATEGORIES = [
    ("1", "10", "간편식사"),
    ("2", "20", "즉석조리"),
    ("3", "30", "과자류"),
    ("4", "40", "아이스크림"),
    ("5", "50", "식품"),
    ("6", "60", "음료"),
]

BASE = Path(__file__).resolve().parent
OUT = BASE / "cu_output"
IMAGES = OUT / "images"
DEBUG = OUT / "debug"

PRODUCTS_FILE = OUT / "products.csv"
STATE_FILE = OUT / "crawl_state.json"
LIST_STATE_FILE = OUT / "list_state.json"
CATEGORY_REPORT_FILE = OUT / "category_report.csv"

SKIP_FILE = BASE / "cu_review" / "skip_website_ids.json"

DELAY = 1.5
RETRIES = 3
MAX_PAGES = 500

TERMINAL_STATUSES = {
    "NO_MATCH_IN_SEARCH_RESPONSE",
    "NO_ON_ITEM_NO",
    "NO_MST_NOTI",
    "AMBIGUOUS",
}

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/svg+xml": ".svg",
}

# price, event 컬럼 추가
CSV_FIELDS = [
    "category_name",
    "website_product_id",
    "product_name",
    "price",
    "event",
    "item_cd",
    "list_image_url",
    "on_item_no",
    "pocketcu_product_name",
    "nutrition_image_urls",
    "image_files",
    "status",
    "error",
]

REPORT_FIELDS = [
    "category_name",
    "product_count",
    "end_reason",
]


# ============================================================
# 공통 파일 처리
# ============================================================

def load_json(path, default):
    if not path.exists():
        return default

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv(path, fields, rows):
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    temporary.replace(path)


def backup_once(path):
    if not path.exists():
        return

    backup = path.with_name(path.name + ".before_resume.bak")

    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"원본 백업: {backup.name}")


def split_values(value):
    return [
        part.strip()
        for part in (value or "").split(" | ")
        if part.strip()
    ]


def usable_file(value):
    if not value:
        return None

    path = Path(value)
    candidates = [path] if path.is_absolute() else [BASE / path]
    candidates.append(IMAGES / path.name)

    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate

    return None


def completed(record):
    files = record.get("image_files") or []

    return (
        record.get("status") == "OK"
        and bool(files)
        and all(usable_file(value) is not None for value in files)
    )


def recover_code(image_url):
    stem = Path(
        unquote(urlparse(image_url or "").path)
    ).stem

    match = re.fullmatch(r"(\d{12,13})(?:_.+)?", stem)
    return match.group(1) if match else ""


# ============================================================
# 시간 및 진행률
# ============================================================

def format_duration(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}시간 {minutes}분 {seconds}초"
    if minutes:
        return f"{minutes}분 {seconds}초"
    return f"{seconds}초"


def print_progress(started_at, finished, total):
    elapsed = time.monotonic() - started_at

    if not total:
        print("[진행] 새로 처리할 상품이 없습니다.")
        return

    percent = finished / total * 100

    print(f"\n[진행] {finished}/{total}개 ({percent:.1f}%)")
    print(f"현재 시각: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"경과 시간: {format_duration(elapsed)}")

    if not finished:
        print("첫 상품 처리 후 예상 종료 시각을 계산합니다.")
        return

    average = elapsed / finished
    remaining = average * max(0, total - finished)

    print(f"상품당 평균: {average:.1f}초")
    print(f"예상 남은 시간: {format_duration(remaining)}")

    if finished >= total:
        print("처리 대상 전체 완료")
    else:
        estimated_end = datetime.now() + timedelta(seconds=remaining)
        print(f"예상 종료 시각: {estimated_end:%Y-%m-%d %H:%M:%S}")


# ============================================================
# 네트워크 요청
# ============================================================

def request(session, method, url, **kwargs):
    for attempt in range(1, RETRIES + 1):
        time.sleep(DELAY)

        try:
            response = session.request(
                method,
                url,
                timeout=(10, 60),
                **kwargs,
            )
            response.raise_for_status()
            return response

        except (requests.ConnectionError, requests.Timeout):
            if attempt == RETRIES:
                raise

        except requests.HTTPError as error:
            status = error.response.status_code
            retryable = status == 429 or 500 <= status < 600

            if not retryable or attempt == RETRIES:
                raise

        print(f"  요청 재시도: {attempt}/{RETRIES}")
        time.sleep(3 * attempt)

    raise RuntimeError("요청을 완료하지 못했습니다.")


# ============================================================
# 홈페이지 목록 수집 (가격 및 행사 정보 추출)
# ============================================================

def parse_products(html):
    soup = BeautifulSoup(html, "html.parser")
    products = []

    for item in soup.select("li.prod_list"):
        name = item.select_one(".name p")
        image = item.select_one(".prod_wrap .prod_img img")
        clickable = item.select_one("[onclick*='view(']")

        # 가격 엘리먼트 탐색
        price_elem = (
            item.select_one(".price strong")
            or item.select_one(".price")
            or item.select_one(".prod_price")
        )

        # 행사 뱃지 엘리먼트 탐색 (1+1, 2+1, 할인 등)
        badge_elems = item.select(".badge li") or item.select(".badge span")

        if name is None or image is None or clickable is None:
            raise ValueError("상품 목록 HTML 구조를 확인해야 합니다.")

        id_match = re.search(
            r"view\s*\(\s*['\"]?(\d+)['\"]?\s*\)",
            clickable.get("onclick", ""),
        )

        if not id_match:
            raise ValueError("홈페이지 상품 ID 추출 실패")

        src = image.get("src") or image.get("data-src") or ""
        if not src.strip():
            raise ValueError("상품 이미지 주소가 없습니다.")

        image_url = urljoin(WEB, src.strip())

        # 가격 추출 (숫자만 정제)
        price_val = ""
        if price_elem:
            digits = re.sub(r"[^\d]", "", price_elem.get_text())
            if digits:
                price_val = digits

        # 행사 정보 추출 (예: '1+1', '2+1', 복수개인 경우 슬래시 구분)
        event_badges = []
        for b in badge_elems:
            txt = b.get_text(strip=True)
            if txt and txt not in event_badges:
                event_badges.append(txt)
        event_val = " / ".join(event_badges) if event_badges else ""

        products.append({
            "website_product_id": id_match.group(1),
            "product_name": name.get_text(" ", strip=True),
            "price": price_val,
            "event": event_val,
            "item_cd": recover_code(image_url),
            "list_image_url": image_url,
        })

    return products


def export_category_report(list_state):
    rows = []

    for _, code, name in CATEGORIES:
        entry = list_state.get(code, {})

        rows.append({
            "category_name": name,
            "product_count": len(entry.get("products", [])),
            "end_reason": entry.get(
                "end_reason", "PENDING"
            ),
        })

    write_csv(CATEGORY_REPORT_FILE, REPORT_FIELDS, rows)


def collect_category(session, depth3, code, name, list_state):
    entry = list_state.setdefault(code, {
        "products": [],
        "next_page": 1,
        "complete": False,
        "signatures": [],
        "end_reason": "PENDING",
    })

    if entry.get("complete"):
        print(
            f"[목록 유지] {name}: "
            f"{len(entry['products'])}개"
        )
        return

    seen = {
        product["website_product_id"]: product
        for product in entry["products"]
    }

    signatures = {
        tuple(value)
        for value in entry.get("signatures", [])
    }

    referer = (
        f"{WEB}/product/product.do"
        f"?category=product&depth2=4&depth3={depth3}"
    )

    start_page = entry.get("next_page", 1)

    for page in range(start_page, MAX_PAGES + 1):
        response = None

        payload = {
            "pageIndex": str(page),
            "searchMainCategory": code,
            "searchSubCategory": "",
            "listType": "",
            "searchCondition": "setA",
            "searchUseYn": "",
            "gdIdx": "0",
            "codeParent": code,
            "user_id": "",
            "search1": "",
            "search2": "",
            "searchKeyword": "",
        }

        try:
            response = request(
                session,
                "POST",
                f"{WEB}/product/productAjax.do",
                data=payload,
                headers={
                    "Referer": referer,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

            if urlparse(response.url).path != "/product/productAjax.do":
                raise ValueError(
                    f"다른 페이지로 이동했습니다: {response.url}"
                )

            products = parse_products(response.content)

            if not products:
                soup = BeautifulSoup(
                    response.content, "html.parser"
                )
                nothing = soup.select_one("#nothing")

                if (
                    nothing is not None
                    and "조회된 상품이 없습니다"
                    in nothing.get_text(" ", strip=True)
                ):
                    entry["complete"] = True
                    entry["end_reason"] = (
                        f"END_NO_PRODUCTS: page={page}"
                    )
                    save_json(LIST_STATE_FILE, list_state)
                    export_category_report(list_state)

                    print(
                        f"[목록 완료] {name}: "
                        f"{len(seen)}개"
                    )
                    return

                raise ValueError(
                    "상품도 없고 정상 종료 안내도 없습니다."
                )

            signature = tuple(
                product["website_product_id"]
                for product in products
            )

            if signature in signatures:
                raise ValueError("이전에 받은 목록이 반복됩니다.")

            new_count = 0

            for product in products:
                key = product["website_product_id"]

                if key not in seen:
                    product["category_name"] = name
                    seen[key] = product
                    new_count += 1

            if not new_count:
                raise ValueError("신규 상품이 추가되지 않았습니다.")

            signatures.add(signature)
            entry["products"] = list(seen.values())
            entry["signatures"].append(list(signature))
            entry["next_page"] = page + 1
            entry["end_reason"] = (
                f"IN_PROGRESS: last_page={page}"
            )

            save_json(LIST_STATE_FILE, list_state)
            export_category_report(list_state)

            print(
                f"[목록] {name} page={page} "
                f"응답={len(products)} "
                f"신규={new_count} 누적={len(seen)}"
            )

        except (requests.RequestException, ValueError) as error:
            entry["end_reason"] = (
                f"INCOMPLETE: page={page}; {error}"
            )

            save_json(LIST_STATE_FILE, list_state)
            export_category_report(list_state)

            (DEBUG / f"list_error_{code}_{page}.txt").write_text(
                str(error), encoding="utf-8"
            )

            if response is not None:
                (DEBUG / f"list_error_{code}_{page}.html").write_bytes(
                    response.content
                )

            raise RuntimeError(
                f"{name} 목록 수집 실패: {error}\n"
                "진행 기록은 저장됐습니다. 재실행하면 해당 페이지부터 재개합니다."
            ) from error

    entry["end_reason"] = (
        f"INCOMPLETE: 최대 페이지 수 {MAX_PAGES} 도달"
    )
    save_json(LIST_STATE_FILE, list_state)
    export_category_report(list_state)

    raise RuntimeError(entry["end_reason"])


def read_products_csv():
    with PRODUCTS_FILE.open(
        newline="", encoding="utf-8-sig"
    ) as file:
        reader = csv.DictReader(file)

        required = {
            "website_product_id",
            "product_name",
            "item_cd",
            "list_image_url",
        }

        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("products.csv에 필수 열이 없습니다.")

        products = list(reader)

    if not products:
        raise ValueError("products.csv에 상품이 없습니다.")

    return products


def get_products(session, force_refresh=False):
    # force_refresh=True 이거나 LIST_STATE가 미완료일 때 새로 웹페이지 수집
    if not force_refresh:
        if LIST_STATE_FILE.exists():
            list_state = load_json(LIST_STATE_FILE, {})

            if isinstance(list_state, dict):
                all_complete = all(
                    list_state.get(code, {}).get("complete")
                    for _, code, _ in CATEGORIES
                )

                if all_complete and PRODUCTS_FILE.exists():
                    print("기존 CSV를 사용합니다. 목록은 다시 수집하지 않습니다.")
                    return read_products_csv()

        elif PRODUCTS_FILE.exists():
            print(
                "기존 CSV를 사용합니다.\n"
                "목록 수집 기록이 없어 기존 CSV를 수집 완료 목록으로 간주합니다."
            )
            return read_products_csv()

    list_state = {}
    print("\n===== 홈페이지 상품 목록 수집 (가격 및 행사 정보 포함) =====")

    for depth3, code, name in CATEGORIES:
        collect_category(
            session, depth3, code, name, list_state
        )

    products = []

    for _, code, _ in CATEGORIES:
        products.extend(list_state[code]["products"])

    if not products:
        raise ValueError("수집한 상품이 없습니다.")

    return products


# ============================================================
# 포켓CU 검색 및 이미지 추출
# ============================================================

def search_products(session, name):
    response = request(
        session,
        "POST",
        f"{POCKET}/api/search/rest/total/main",
        json={
            "searchWord": name,
            "prevSearchWord": "",
            "spellModifyUseYn": "Y",
            "searchSort": "recom",
        },
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": POCKET,
            "Referer": f"{POCKET}/search/total/product/main",
            "AJAX": "true",
            "X-Requested-With": "XMLHttpRequest",
        },
    )

    data = response.json()

    if not isinstance(data, dict) or data.get("resp_cd") != "0000":
        raise ValueError("포켓CU 검색 응답 오류")

    sections = data.get("data")

    if not isinstance(sections, dict):
        raise ValueError("검색 응답에 data 객체가 없습니다.")

    candidates = {}

    for section_name in (
        "stockResult",
        "pickupResult",
        "delvResult",
        "delvPickupResult",
    ):
        section = sections.get(section_name) or {}
        result = section.get("result") or {}

        for row in result.get("rows") or []:
            fields = row.get("fields") or {}

            item_cd = str(fields.get("item_cd") or "").strip()
            product_id = str(fields.get("on_item_no") or "").strip()

            if not item_cd:
                continue

            candidates[(item_cd, product_id)] = {
                "item_cd": item_cd,
                "on_item_no": product_id,
                "name": (
                    fields.get("prd_disp_nm")
                    or fields.get("item_nm")
                    or ""
                ),
            }

    return list(candidates.values())


def get_nutrition_urls(session, product_id):
    page_url = f"{POCKET}/product/info1/{product_id}"
    response = request(session, "GET", page_url)

    if (
        urlparse(response.url).path.rstrip("/")
        != f"/product/info1/{product_id}"
    ):
        raise ValueError(
            f"다른 페이지로 이동했습니다: {response.url}"
        )

    soup = BeautifulSoup(response.content, "html.parser")
    urls = []

    for image in soup.select("img"):
        for attr in ("src", "data-src", "data-original"):
            value = image.get(attr)

            if not value:
                continue

            url = urljoin(response.url, value.strip())
            parsed = urlparse(url)

            if (
                parsed.scheme in ("http", "https")
                and "/mst_noti/" in unquote(parsed.path).lower()
                and url not in urls
            ):
                urls.append(url)

    return page_url, urls


def download_image(session, url, referer, product_id, index):
    suffix = "" if index == 1 else f"_{index}"
    stem = f"{product_id}{suffix}"

    for extension in sorted(set(IMAGE_EXTENSIONS.values())):
        path = IMAGES / f"{stem}{extension}"

        if path.is_file() and path.stat().st_size > 0:
            print(f"  기존 이미지 유지: {path.name}")
            return str(path), False

    response = request(
        session,
        "GET",
        url,
        headers={"Referer": referer},
    )

    content_type = response.headers.get(
        "Content-Type", ""
    ).split(";")[0].strip().lower()

    extension = IMAGE_EXTENSIONS.get(content_type)

    if not extension:
        raise ValueError(
            f"지원하지 않는 이미지 응답: {content_type}"
        )

    if not response.content:
        raise ValueError("이미지 응답이 비어 있습니다.")

    path = IMAGES / f"{stem}{extension}"
    temporary = path.with_suffix(path.suffix + ".part")

    temporary.write_bytes(response.content)
    temporary.replace(path)

    print(f"  다운로드: {path.name}")
    return str(path), True


# ============================================================
# 진행 기록과 결과 CSV
# ============================================================

def record_from_csv(row):
    return {
        "on_item_no": row.get("on_item_no", ""),
        "pocketcu_product_name": row.get(
            "pocketcu_product_name", ""
        ),
        "nutrition_image_urls": split_values(
            row.get("nutrition_image_urls", "")
        ),
        "image_files": split_values(row.get("image_files", "")),
        "status": row.get("status") or "PENDING",
        "error": row.get("error", ""),
    }


def prepare_products(products, state, skip_ids):
    recovered_count = 0

    for product in products:
        original = product.get("item_cd", "").strip()
        recovered = recover_code(product.get("list_image_url", ""))

        code = (
            original
            if re.fullmatch(r"\d{12,13}", original)
            else recovered
        )

        if code and code != original:
            recovered_count += 1

        product["item_cd"] = code
        product["_skip"] = (
            product.get("website_product_id", "").strip()
            in skip_ids
        )

        if not code:
            continue

        csv_record = record_from_csv(product)

        if csv_record["status"] == "NO_ITEM_CD":
            csv_record["status"] = "PENDING"
            csv_record["error"] = ""

        if csv_record["status"] == "SKIPPED":
            csv_record["status"] = "PENDING"
            csv_record["error"] = ""

        existing = state.get(code)

        if existing is None:
            state[code] = csv_record
        elif not completed(existing) and completed(csv_record):
            state[code] = csv_record

    return recovered_count


def export_results(products, state):
    rows = []

    for product in products:
        code = product["item_cd"]
        record = state.get(code, {}) if code else {}

        row = {
            field: product.get(field, "")
            for field in CSV_FIELDS
        }

        row.update({
            "on_item_no": record.get("on_item_no", ""),
            "pocketcu_product_name": record.get(
                "pocketcu_product_name", ""
            ),
            "nutrition_image_urls": " | ".join(
                record.get("nutrition_image_urls") or []
            ),
            "image_files": " | ".join(
                record.get("image_files") or []
            ),
            "status": record.get("status", "PENDING"),
            "error": record.get("error", ""),
        })

        if product.get("_skip"):
            row["status"] = "SKIPPED"
            row["error"] = "제외 목록에 따라 처리에서 건너뜀"

        elif not code:
            row["status"] = "NO_ITEM_CD"
            row["error"] = "이미지 파일명에서 상품 코드 추출 실패"

        rows.append(row)

    write_csv(PRODUCTS_FILE, CSV_FIELDS, rows)


# ============================================================
# 개별 상품 다운로드 처리
# ============================================================

def process_product(
    session,
    product,
    previous,
    search_cache,
    checkpoint,
    counts,
):
    record = {
        "on_item_no": previous.get("on_item_no", ""),
        "pocketcu_product_name": previous.get(
            "pocketcu_product_name", ""
        ),
        "nutrition_image_urls": list(
            previous.get("nutrition_image_urls") or []
        ),
        "image_files": list(previous.get("image_files") or []),
        "status": "IN_PROGRESS",
        "error": "",
    }

    try:
        product_id = str(record["on_item_no"]).strip()

        if not re.fullmatch(r"\d+", product_id):
            name = product["product_name"]

            if name not in search_cache:
                search_cache[name] = search_products(session, name)

            exact = [
                candidate
                for candidate in search_cache[name]
                if candidate["item_cd"] == product["item_cd"]
            ]

            valid = {
                candidate["on_item_no"]: candidate
                for candidate in exact
                if re.fullmatch(r"\d+", candidate["on_item_no"])
            }

            if not valid:
                record["status"] = (
                    "NO_MATCH_IN_SEARCH_RESPONSE"
                    if not exact
                    else "NO_ON_ITEM_NO"
                )
                record["error"] = (
                    "현재 검색 응답에서 유효한 상품 ID를 확보하지 못함"
                )
                checkpoint(record)
                return record

            if len(valid) > 1:
                record["status"] = "AMBIGUOUS"
                record["error"] = (
                    "동일 코드에 여러 상품 ID: "
                    + ", ".join(sorted(valid))
                )
                checkpoint(record)
                return record

            product_id, match = next(iter(valid.items()))
            record["on_item_no"] = product_id
            record["pocketcu_product_name"] = match["name"]
            checkpoint(record)

        page_url = f"{POCKET}/product/info1/{product_id}"
        urls = record["nutrition_image_urls"]

        if not urls:
            page_url, urls = get_nutrition_urls(
                session, product_id
            )
            record["nutrition_image_urls"] = urls
            checkpoint(record)

        if not urls:
            record["status"] = "NO_MST_NOTI"
            record["error"] = "mst_noti 이미지 태그 없음"
            checkpoint(record)
            return record

        record["image_files"] = []
        checkpoint(record)

        for index, url in enumerate(urls, start=1):
            saved, downloaded = download_image(
                session, url, page_url, product_id, index
            )

            record["image_files"].append(saved)

            label = (
                "새로 다운로드한 이미지"
                if downloaded
                else "기존 이미지 재사용"
            )
            counts[label] += 1
            checkpoint(record)

        record["status"] = "OK"
        record["error"] = ""

    except (requests.RequestException, ValueError, OSError) as error:
        record["status"] = "ERROR"
        record["error"] = str(error)

    checkpoint(record)
    return record


# ============================================================
# 다운로드 실행
# ============================================================

def run_downloads(session, products, state, retry_unresolved):
    counts = Counter()
    search_cache = {}
    queue = []
    seen_codes = set()

    for product in products:
        code = product["item_cd"]

        if product["_skip"]:
            counts["제외 목록으로 건너뛴 행"] += 1
            continue

        if not code:
            counts["코드가 없어 건너뛴 행"] += 1
            continue

        if code in seen_codes:
            counts["중복 코드로 건너뛴 행"] += 1
            continue

        seen_codes.add(code)
        previous = state.get(code, {})

        if completed(previous):
            counts["이미 완료된 상품"] += 1
            continue

        if (
            not retry_unresolved
            and previous.get("status") in TERMINAL_STATUSES
        ):
            counts["이전 미해결 상품 보류"] += 1
            continue

        queue.append(product)

    def persist():
        save_json(STATE_FILE, state)
        export_results(products, state)

    started_at = time.monotonic()
    finished = 0
    interrupted = False

    print("\n===== 포켓CU 검색 및 이미지 다운로드 =====")
    print(f"시작 시각: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"실제 처리 대상: {len(queue)}개")

    if queue:
        print("첫 상품 처리 후 예상 종료 시각을 계산합니다.")
    else:
        print("새로 처리할 상품이 없습니다.")

    try:
        for index, product in enumerate(queue, start=1):
            code = product["item_cd"]

            print(
                f"\n[{index}/{len(queue)}] "
                f"{product['product_name']} / {code}"
            )

            def checkpoint(record):
                state[code] = {
                    **record,
                    "nutrition_image_urls": list(
                        record.get("nutrition_image_urls") or []
                    ),
                    "image_files": list(
                        record.get("image_files") or []
                    ),
                }
                save_json(STATE_FILE, state)

            record = process_product(
                session,
                product,
                state.get(code, {}),
                search_cache,
                checkpoint,
                counts,
            )

            counts[f"이번 처리 {record['status']}"] += 1
            persist()
            finished += 1

            print(
                f"  {record['status']}"
                + (
                    f": {record['error']}"
                    if record["error"]
                    else ""
                )
            )

            print_progress(started_at, finished, len(queue))

    except KeyboardInterrupt:
        interrupted = True
        print("\n사용자가 중단했습니다. 진행 상황을 저장합니다.")

    finally:
        persist()

        print(f"\n종료 시각: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(
            "다운로드 단계 실행 시간: "
            + format_duration(time.monotonic() - started_at)
        )

        print("\n===== 이번 실행 결과 =====")
        print(f"처리한 상품: {finished}/{len(queue)}개")

        for label, count in sorted(counts.items()):
            print(f"{label}: {count}")

        if interrupted:
            print("\n같은 명령으로 다시 실행하면 이어서 처리합니다.")

        print("진행 기록과 products.csv를 저장했습니다.")


# ============================================================
# 메인
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="CU 상품 목록 및 영양정보 이미지 수집"
    )

    parser.add_argument(
        "--list-only",
        action="store_true",
        help="목록과 CSV만 생성하고 이미지는 다운로드하지 않음",
    )

    parser.add_argument(
        "--retry-unresolved",
        action="store_true",
        help="이전 검색 실패·이미지 없음 등의 상품도 재시도",
    )

    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)
    DEBUG.mkdir(parents=True, exist_ok=True)

    state = load_json(STATE_FILE, {})

    if not isinstance(state, dict):
        raise ValueError("crawl_state.json 형식 오류")

    skip_values = load_json(SKIP_FILE, [])

    if not isinstance(skip_values, list):
        raise ValueError("제외 목록은 JSON 배열이어야 합니다.")

    skip_ids = {
        str(value).strip()
        for value in skip_values
    }

    backup_once(PRODUCTS_FILE)
    backup_once(STATE_FILE)

    with requests.Session() as session:
        session.trust_env = False
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "ko-KR,ko;q=0.9",
        })

        products = get_products(session)

        recovered_count = prepare_products(
            products, state, skip_ids
        )

        save_json(STATE_FILE, state)
        export_results(products, state)

        unique_codes = {
            product["item_cd"]
            for product in products
            if product["item_cd"]
        }

        print("\n===== 상품 목록 요약 =====")
        print(f"카테고리-상품 행: {len(products)}")
        print(f"고유 상품 코드: {len(unique_codes)}")
        print(f"기존 값에서 코드 복구: {recovered_count}행")
        print(f"선택 제외 목록: {len(skip_ids)}개 ID")

        if args.list_only:
            print("\n목록 전용 실행 완료. products.csv를 저장했습니다.")
            return

        run_downloads(
            session,
            products,
            state,
            args.retry_unresolved,
        )


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print(
            "\n사용자가 중단했습니다. "
            "이미 저장된 진행 기록과 파일은 유지됩니다."
        )

    except (
        requests.RequestException,
        ValueError,
        OSError,
        RuntimeError,
    ) as error:
        print(f"\n[실행 오류] {error}")
        raise SystemExit(1)