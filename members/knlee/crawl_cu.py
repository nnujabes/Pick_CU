"""
CU 카테고리별 이미지 수집 실행 프로그램

필수 파일:
    crawl_cu.py
    crawl_cu_core.py

실행 예:
    # 1) 가격 및 이벤트 정보만 빠르게 다시 수집 (이미지 다운로드 X)
    python crawl_cu.py --categories 1 2 3 4 5 6 --list-only --refresh-list

    # 2) 일반 다운로드 실행
    python crawl_cu.py --categories 1 2
"""

import argparse
import copy
import csv
import json
import shutil
import time
from pathlib import Path

import requests

import crawl_cu_core as core


BASE = Path(__file__).resolve().parent
ROOT = BASE / "cu_output"
IMAGE_ROOT = ROOT / "images"
CATEGORY_ROOT = ROOT / "categories"

LEGACY_CSV = ROOT / "products.csv"
LEGACY_STATE = ROOT / "crawl_state.json"

SKIP_FILE = BASE / "cu_review" / "skip_website_ids.json"

CATEGORY_CONFIG = {
    1: ("1", "10", "간편식사", "01_간편식사"),
    2: ("2", "20", "즉석조리", "02_즉석조리"),
    3: ("3", "30", "과자류", "03_과자류"),
    4: ("4", "40", "아이스크림", "04_아이스크림"),
    5: ("5", "50", "식품", "05_식품"),
    6: ("6", "60", "음료", "06_음료"),
}

CSV_FIELDS = core.CSV_FIELDS


# ============================================================
# 공통 처리
# ============================================================

def read_csv(path):
    if not path.exists():
        return []

    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:
        return list(csv.DictReader(file))


def read_json(path, default):
    if not path.exists():
        return default

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def validate_categories(categories):
    if isinstance(categories, int):
        categories = [categories]

    result = []

    for value in categories:
        value = int(value)

        if value not in CATEGORY_CONFIG:
            raise ValueError(
                f"카테고리는 1~6만 가능합니다: {value}"
            )

        if value not in result:
            result.append(value)

    if not result:
        raise ValueError("카테고리를 하나 이상 지정하세요.")

    return result


def create_category_folders():
    ROOT.mkdir(parents=True, exist_ok=True)
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    CATEGORY_ROOT.mkdir(parents=True, exist_ok=True)

    for _, _, _, folder in CATEGORY_CONFIG.values():
        (IMAGE_ROOT / folder).mkdir(
            parents=True,
            exist_ok=True,
        )
        (CATEGORY_ROOT / folder / "debug").mkdir(
            parents=True,
            exist_ok=True,
        )


def path_basename(value):
    return str(value).replace("\\", "/").rsplit("/", 1)[-1]


def split_files(value):
    return [
        part.strip()
        for part in (value or "").split(" | ")
        if part.strip()
    ]


def nonempty_file(path):
    return path.is_file() and path.stat().st_size > 0


# ============================================================
# 기존 평면 폴더의 이미지 재사용
# ============================================================

def collect_old_filenames(rows, legacy_state):
    filenames = set()
    product_ids = set()

    for row in rows:
        for value in split_files(row.get("image_files", "")):
            filenames.add(path_basename(value))

        code = row.get("item_cd", "").strip()
        record = legacy_state.get(code, {})

        for value in record.get("image_files") or []:
            filenames.add(path_basename(value))

        for value in (
            row.get("on_item_no", ""),
            record.get("on_item_no", ""),
        ):
            value = str(value).strip()

            if value.isdigit():
                product_ids.add(value)

    extensions = set(core.IMAGE_EXTENSIONS.values())

    for product_id in product_ids:
        for path in IMAGE_ROOT.glob(f"{product_id}*"):
            if (
                path.is_file()
                and path.suffix.lower() in extensions
                and (
                    path.stem == product_id
                    or (
                        path.stem.startswith(product_id + "_")
                        and path.stem[len(product_id) + 1:].isdigit()
                    )
                )
            ):
                filenames.add(path.name)

    return filenames


def copy_existing_images(rows, destination, legacy_state):
    copied = 0

    for filename in sorted(
        collect_old_filenames(rows, legacy_state)
    ):
        source = IMAGE_ROOT / filename
        target = destination / filename

        if nonempty_file(target):
            continue

        if not nonempty_file(source):
            continue

        temporary = target.with_suffix(target.suffix + ".part")

        shutil.copy2(source, temporary)
        temporary.replace(target)
        copied += 1

    return copied


def rebase_record(record, destination):
    result = copy.deepcopy(record)

    result["image_files"] = [
        str(destination / path_basename(value))
        for value in result.get("image_files") or []
        if value
    ]

    return result


def rebase_csv_rows(rows, destination):
    for row in rows:
        row["image_files"] = " | ".join(
            str(destination / path_basename(value))
            for value in split_files(
                row.get("image_files", "")
            )
        )


# ============================================================
# 카테고리별 초기화
# ============================================================

def prepare_category(category, legacy_rows, legacy_state):
    _, _, name, folder = CATEGORY_CONFIG[category]

    work = CATEGORY_ROOT / folder
    images = IMAGE_ROOT / folder

    csv_path = work / "products.csv"
    state_path = work / "crawl_state.json"

    seed_rows = [
        dict(row)
        for row in legacy_rows
        if row.get("category_name", "").strip() == name
    ]

    local_rows = read_csv(csv_path)

    if not csv_path.exists() and seed_rows:
        rebase_csv_rows(seed_rows, images)
        core.write_csv(
            csv_path,
            CSV_FIELDS,
            seed_rows,
        )
        local_rows = seed_rows
        print(f"[목록 분리] {name}: {len(seed_rows)}행")

    copied = copy_existing_images(
        seed_rows + local_rows,
        images,
        legacy_state,
    )

    state = read_json(state_path, {})

    if not isinstance(state, dict):
        raise ValueError(f"진행 기록 형식 오류: {state_path}")

    for row in local_rows:
        code = row.get("item_cd", "").strip()

        if code and code not in state and code in legacy_state:
            state[code] = copy.deepcopy(legacy_state[code])

    state = {
        code: rebase_record(record, images)
        for code, record in state.items()
    }

    core.save_json(state_path, state)

    if copied:
        print(f"[기존 이미지 분류] {name}: {copied}개 복사")

    return work, images


# ============================================================
# 기존 수집 모듈을 현재 카테고리에 연결
# ============================================================

def configure_core(category, delay):
    depth3, code, name, folder = CATEGORY_CONFIG[category]

    work = CATEGORY_ROOT / folder
    images = IMAGE_ROOT / folder

    core.BASE = BASE
    core.OUT = work
    core.IMAGES = images
    core.DEBUG = work / "debug"

    core.PRODUCTS_FILE = work / "products.csv"
    core.STATE_FILE = work / "crawl_state.json"
    core.LIST_STATE_FILE = work / "list_state.json"
    core.CATEGORY_REPORT_FILE = work / "category_report.csv"

    core.CATEGORIES = [(depth3, code, name)]
    core.DELAY = delay


def load_skip_ids():
    values = read_json(SKIP_FILE, [])

    if not isinstance(values, list):
        raise ValueError("제외 목록은 JSON 배열이어야 합니다.")

    return {str(value).strip() for value in values}


# ============================================================
# 공개 실행 함수
# ============================================================

def run_categories(
    categories,
    list_only=False,
    prepare_only=False,
    retry_unresolved=False,
    refresh_list=False,
    delay=0.5,
):
    categories = validate_categories(categories)

    if delay < 0:
        raise ValueError("delay는 0 이상이어야 합니다.")

    create_category_folders()

    legacy_rows = read_csv(LEGACY_CSV)
    legacy_state = read_json(LEGACY_STATE, {})

    if not isinstance(legacy_state, dict):
        raise ValueError("기존 crawl_state.json 형식 오류")

    skip_ids = load_skip_ids()
    started = time.monotonic()

    print("선택한 카테고리:")
    for category in categories:
        print(f"- {category}: {CATEGORY_CONFIG[category][2]}")

    print(f"요청 전 대기 시간: {delay}초")

    for category in categories:
        name = CATEGORY_CONFIG[category][2]

        print(f"\n{'=' * 60}")
        print(f"카테고리 {category}: {name}")
        print(f"{'=' * 60}")

        work, images = prepare_category(
            category,
            legacy_rows,
            legacy_state,
        )

        if prepare_only:
            continue

        configure_core(category, delay)

        state = read_json(core.STATE_FILE, {})

        with requests.Session() as session:
            session.trust_env = False
            session.headers.update({
                "User-Agent": core.USER_AGENT,
                "Accept-Language": "ko-KR,ko;q=0.9",
            })

            # refresh_list=True 이면 기존 CSV 캐시 무시하고 웹에서 신규 수집
            products = core.get_products(session, force_refresh=refresh_list)

            rebase_csv_rows(products, images)

            core.prepare_products(
                products,
                state,
                skip_ids,
            )

            state = {
                code: rebase_record(record, images)
                for code, record in state.items()
            }

            core.save_json(core.STATE_FILE, state)
            core.export_results(products, state)

            if list_only:
                print(f"[목록 완료] {name}: {len(products)}행")
                continue

            core.run_downloads(
                session,
                products,
                state,
                retry_unresolved,
            )

        print(f"\n[{name}] 이미지 폴더: {images}")
        print(f"[{name}] 결과 CSV: {work / 'products.csv'}")

        pending = [
            product
            for product in products
            if (
                not product.get("_skip")
                and product.get("item_cd")
                and state.get(product["item_cd"], {}).get(
                    "status", "PENDING"
                ) in {"PENDING", "IN_PROGRESS"}
            )
        ]

        if pending:
            print(
                "\n아직 미처리·처리 중인 상품이 있어 다음 카테고리 실행을 중단합니다."
            )
            print("같은 명령으로 재실행하면 이어서 처리합니다.")
            break

    elapsed = time.monotonic() - started
    print("\n실행 종료. 경과 시간: " + core.format_duration(elapsed))


def main():
    parser = argparse.ArgumentParser(
        description="CU 카테고리별 이미지 수집"
    )

    parser.add_argument(
        "--categories",
        type=int,
        nargs="+",
        choices=range(1, 7),
        help="처리할 카테고리 번호. 예: --categories 1 2",
    )

    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="6개 폴더 생성 및 기존 이미지 분류만 수행",
    )

    parser.add_argument(
        "--list-only",
        action="store_true",
        help="선택 카테고리의 목록만 준비",
    )

    parser.add_argument(
        "--refresh-list",
        action="store_true",
        help="기존 CSV 캐시를 무시하고 웹에서 가격/행사 정보를 포함해 목록을 강제 재수집",
    )

    parser.add_argument(
        "--retry-unresolved",
        action="store_true",
        help="이전 검색 실패·이미지 없음도 재시도",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="요청 전 대기 시간(초). 기본 0.5",
    )

    args = parser.parse_args()

    if args.categories:
        categories = args.categories
    elif args.prepare_only:
        categories = list(CATEGORY_CONFIG)
    else:
        parser.error("--categories 1 또는 --categories 1 2처럼 카테고리를 지정하세요.")

    run_categories(
        categories=categories,
        list_only=args.list_only,
        prepare_only=args.prepare_only,
        retry_unresolved=args.retry_unresolved,
        refresh_list=args.refresh_list,
        delay=args.delay,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단했습니다. 저장된 목록·진행 기록·이미지는 유지됩니다.")
    except (requests.RequestException, ValueError, OSError, RuntimeError) as error:
        print(f"\n[오류] {error}")
        raise SystemExit(1)