"""CU 영양성분표 이미지에서 영양소 6개를 추출하고 검증해 products.csv에 반영한다.

처리 순서
    1. Qwen2.5-VL로 이미지마다 영양정보를 JSON으로 추출한다.
    2. 기준량 표기를 정리하고, % 비율과 열량 계산으로 값을 검증한다.
    3. 상품을 DB 포함 / 검수 필요 / 성분 누락 / 영양표 없음 / 실패로 분류해 결과 CSV에 저장한다.
    4. --apply를 주면 DB 포함 상품의 값을 products.csv에 반영한다.

사용법
    python vlm_nutrition_parser.py                                  # 전체 추론, 결과 CSV만 저장
    python vlm_nutrition_parser.py --categories 01_간편식사 --limit 10  # 일부만 시험
    python vlm_nutrition_parser.py --load-in-4bit                   # 8GB GPU용 4-bit 양자화
    python vlm_nutrition_parser.py --apply                          # 추론 후 products.csv 반영
    python vlm_nutrition_parser.py --apply-only                     # 저장된 결과 CSV만 반영
    python vlm_nutrition_parser.py --self-check                     # 모델 없이 검증 코드 점검

결과 CSV는 이미지 단위로 바로 저장하므로, 중단 후 다시 실행하면 처리한 이미지를 건너뛴다.
RTX 4090(bf16)에서 이미지당 약 4초, 최대 VRAM 약 16GB가 걸렸다.
"""
import argparse
import csv
import json
import re
import shutil
import time
import warnings
from collections import Counter
from pathlib import Path

import pandas as pd
from PIL import Image

# 대형 상세페이지 이미지 허용 및 경고 필터링
Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore", message=".*is not aligned for fast kernel.*")

# ========================================================
# 설정
# ========================================================
MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
PATCH_SIZE = 14
MIN_PIXELS = 256 * 28 * 28
MAX_PIXELS = 2560 * 28 * 28
MAX_PIXELS_4BIT = 1024 * 28 * 28  # 8GB VRAM 기준
MAX_NEW_TOKENS = 500

CATEGORIES_TO_PROCESS = [
    "01_간편식사",
    "02_즉석조리",
    "03_과자류",
    "04_아이스크림",
    "05_식품",
    "06_음료",
]
RESULT_DIR_NAME = "vlm_results"
RESULT_SUFFIX = "_v7.csv"

OUTCOME_OK = "DB 포함"
OUTCOME_REVIEW = "검수 필요"
OUTCOME_MISSING = "성분 누락"
OUTCOME_NO_TABLE = "영양표 없음"
OUTCOME_FAILED = "실패"

# 검증 기준
CALORIE_DIFF_THRESHOLD = 0.15
MAX_PLAUSIBLE_SODIUM_MG = 5000
MAX_KCAL_PER_UNIT = 9  # 지방 1g의 열량. 기준량 1g(mL)당 이보다 높으면 불가능한 값이다.
PERCENT_TOLERANCE = 1  # %포인트

NUTRIENT_UNITS = {
    "calories": "kcal",
    "sodium": "mg",
    "carbs": "g",
    "sugar": "g",
    "fat": "g",
    "protein": "g",
}
NUTRIENT_LABELS = {
    "calories": "열량",
    "sodium": "나트륨",
    "carbs": "탄수화물",
    "sugar": "당류",
    "fat": "지방",
    "protein": "단백질",
}
RESULT_VALUE_COLUMNS = {
    "calories": "calories_kcal",
    "sodium": "sodium_mg",
    "carbs": "carbs_g",
    "sugar": "sugar_g",
    "fat": "fat_g",
    "protein": "protein_g",
}
AMOUNT_UNIT_SCALE = {"g": ("g", 1), "kg": ("g", 1000), "ml": ("mL", 1), "l": ("mL", 1000)}

# 한국 1일 영양성분 기준치
DAILY_VALUES = {
    "sodium": 2000,
    "carbs": 324,
    "sugar": 100,
    "fat": 54,
    "saturated_fat": 15,
    "cholesterol": 300,
    "protein": 55,
}
CHECK_NAMES = {**NUTRIENT_LABELS, "saturated_fat": "포화지방", "cholesterol": "콜레스테롤"}
CHECK_UNITS = {**NUTRIENT_UNITS, "saturated_fat": "g", "cholesterol": "mg"}

# 포장 환산값이 틀렸거나 의심되어 DB에서 뺀 상품 (2026-11-03 팀 결정)
EXCLUDED_PRODUCTS = {
    "삼)소고기고추장삼각",
    "도)간장불백닭강정더블",
    "샐)치킨너겟&에그샐러드",
}
EXCLUDED_FLAG = "포장 환산값 의심으로 사용자 결정에 따라 제외"

AMOUNT_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(kg|g|ml|l)(?![a-z])", re.IGNORECASE)

SYSTEM_PROMPT = """너는 식품 라벨 이미지의 영양정보 표를 보이는 그대로 옮겨 적는 데이터 추출기다. 추측, 계산, 환산을 하지 마라.

[1단계: 표 찾기]
'영양정보' 또는 '영양성분' 표가 없으면 has_nutrition_table을 false로 하고 나머지 값은 모두 null로 하라.

[2단계: 내용량]
- total_amount와 total_unit: '총 내용량' 또는 '내용량'에 적힌 양. kcal 값이 아니다.
- basis_amount와 basis_unit: 표의 수치가 어떤 양을 기준으로 하는지 라벨에 'OO당'으로 적힌 양. '1개(OOg)당'처럼 무게가 괄호에 있으면 그 무게를 쓴다.
- 'OO당' 표기가 없거나 '총 내용량당'이면 basis는 total과 같은 값이다. 라벨에 없는 기준량을 만들지 마라.
- 단위는 g, kg, mL, L만 쓴다.

[3단계: 영양성분]
각 항목마다 g 또는 mg으로 적힌 양과, 같은 항목의 1일 영양성분 기준치 비율(%)을 따로 옮겨라.
- sodium, sodium_pct: '나트륨'의 mg 값과 % 값
- carbs, carbs_pct: '탄수화물'의 g 값과 % 값
- sugar, sugar_pct: '당류'의 g 값과 % 값. 유당, 알룰로스, 에리스리톨, 식이섬유가 아니다.
- fat, fat_pct: '지방'의 g 값과 % 값. 포화지방, 트랜스지방이 아니다.
- trans_fat: '트랜스지방'의 g 값
- saturated_fat, saturated_fat_pct: '포화지방'의 g 값과 % 값
- cholesterol, cholesterol_pct: '콜레스테롤'의 mg 값과 % 값
- protein, protein_pct: '단백질'의 g 값과 % 값
- calories: '열량' 또는 kcal 값

규칙:
- % 값을 양 칸에 쓰거나, 양을 % 칸에 쓰지 마라. %가 표에 없으면 % 칸은 null이다.
- 표에 항목 이름이 없으면 그 값은 null이다. 0으로 채우지 마라.
- '1g 미만'처럼 정확한 숫자가 아닌 표기는 문자열로 그대로 쓴다.

[출력]
설명이나 마크다운 없이 JSON 객체 하나만 출력하라. 숫자에는 단위와 % 기호를 붙이지 마라.
키: has_nutrition_table, basis_amount, basis_unit, total_amount, total_unit, calories, sodium, sodium_pct, carbs, carbs_pct, sugar, sugar_pct, fat, fat_pct, trans_fat, saturated_fat, saturated_fat_pct, cholesterol, cholesterol_pct, protein, protein_pct"""

USER_PROMPT = "이 이미지에서 영양정보 표의 기준량, 총 내용량, 영양성분 수치를 추출해줘."

RESULT_COLUMNS = [
    "category", "product_name", "price", "image", "outcome", "status", "has_nutrition_table",
    "basis_amount", "basis_unit", "total_amount", "total_unit",
    "calories_kcal", "sodium_mg", "carbs_g", "sugar_g", "fat_g", "protein_g",
    "package_calories_kcal", "package_sodium_mg", "package_carbs_g",
    "package_sugar_g", "package_fat_g", "package_protein_g",
    "flags", "amount_fixes", "elapsed_sec", "raw_output",
]

model = None
processor = None


# ========================================================
# 1. 모델 출력 해석
# ========================================================
def parse_value(val):
    """모델 출력 값을 (숫자, 소문자 단위, 문제 설명)으로 해석한다."""
    if val is None:
        return None, None, None
    if isinstance(val, bool):
        return None, None, f"해석 불가({val})"
    if isinstance(val, (int, float)):
        return float(val), None, None

    text = str(val).strip()
    if text == "" or re.match(r"^(null|none|nan|n/a|-)(\s|$)", text, re.IGNORECASE):
        return None, None, None
    if "%" in text:
        return None, None, f"비율 값({text})"
    if re.search(r"미만|이하|이상|초과|[<>~]", text):
        return None, None, f"정확한 숫자 아님({text})"

    match = re.fullmatch(
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(kcal|mg|kg|g|ml|l)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, None, f"해석 불가({text})"

    number = float(match.group(1).replace(",", ""))
    unit = match.group(2).lower() if match.group(2) else None
    return number, unit, None


def parse_nutrient(val, expected_unit):
    number, unit, problem = parse_value(val)
    if problem:
        return None, problem
    if unit and unit != expected_unit:
        return None, f"단위 불일치({val}, 기대 단위 {expected_unit})"
    return number, None


def parse_amount(amount, unit_field):
    """기준량이나 총 내용량을 g 또는 mL로 통일해 (숫자, 단위, 문제 설명)으로 돌려준다."""
    number, unit, problem = parse_value(amount)
    if problem:
        return None, None, problem
    if number is None:
        return None, None, None

    unit_key = unit or (str(unit_field).strip().lower() if unit_field else None)
    if unit_key not in AMOUNT_UNIT_SCALE:
        return None, None, f"단위 확인 불가({amount}, {unit_field})"

    normalized_unit, scale = AMOUNT_UNIT_SCALE[unit_key]
    return number * scale, normalized_unit, None


def parse_percent(value):
    """'18%', '18 %', 18을 모두 숫자로 읽는다."""
    if value is None or isinstance(value, bool):
        return None
    number, _, problem = parse_value(str(value).replace("%", "").strip())
    return None if problem else number


def load_json_object(text):
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_json(output_text):
    match = re.search(r"\{.*\}", output_text, re.DOTALL)
    if not match:
        return None

    body = match.group(0)
    parsed = load_json_object(body)
    if parsed is None:
        # "fat": 9g, "sodium": 1,440 처럼 따옴표 없는 값은 문자열로 감싸 다시 시도한다
        quoted = re.sub(r':\s*(\d[\d,.]*\s*[a-zA-Z]*)\s*(?=[,}\n])', r': "\1"', body)
        parsed = load_json_object(quoted)
    return parsed


# ========================================================
# 2. 기준량과 총 내용량 정리
# ========================================================
def clean_amount(value, unit_field):
    """(값, 단위, 보정 설명)을 돌려준다. 고칠 필요가 없으면 입력을 그대로 돌려준다.

    '1개(134g)당', '134 g (375 kcal)'처럼 g/mL 값이 하나뿐이면 그 값을 쓰고,
    '190kcal'처럼 열량만 있으면 양으로 인정하지 않는다. g 값이 둘 이상이면 고치지 않는다.
    """
    if value is None:
        return value, unit_field, None
    text = str(value).strip()
    number, unit, problem = parse_value(text)
    if not problem and number is not None:
        if unit == "kcal" or (unit is None and str(unit_field).strip().lower() == "kcal"):
            return None, None, f"열량 값 제외({text})"
        return value, unit_field, None
    if not problem:
        return value, unit_field, None

    found = {(float(n.replace(",", "")), u.lower()) for n, u in AMOUNT_RE.findall(text)}
    if len(found) == 1:
        amount, amount_unit = found.pop()
        return f"{amount:g}{amount_unit}", amount_unit, f"표기 정리({text}→{amount:g}{amount_unit})"
    if not found and "kcal" in text.lower():
        return None, None, f"열량 값 제외({text})"
    return value, unit_field, None


def amount_number(parsed, key):
    number, _, problem = parse_amount(parsed.get(f"{key}_amount"), parsed.get(f"{key}_unit"))
    return None if problem else number


def fill_amounts(parsed):
    """기준량과 총 내용량 중 한쪽만 있으면 다른 쪽에 복사한다."""
    filled = dict(parsed)
    has_basis = parse_value(filled.get("basis_amount"))[0] is not None
    has_total = parse_value(filled.get("total_amount"))[0] is not None
    if has_total and not has_basis:
        filled["basis_amount"], filled["basis_unit"] = filled.get("total_amount"), filled.get("total_unit")
    elif has_basis and not has_total:
        filled["total_amount"], filled["total_unit"] = filled.get("basis_amount"), filled.get("basis_unit")
    return filled


def clean_amounts(parsed):
    """기준량과 총 내용량을 정리해 (정리한 값, 보정 내역)을 돌려준다."""
    cleaned = dict(parsed)
    fixes = []
    for key, name in (("basis", "기준량"), ("total", "총 내용량")):
        cleaned[f"{key}_amount"], cleaned[f"{key}_unit"], note = clean_amount(
            parsed.get(f"{key}_amount"), parsed.get(f"{key}_unit")
        )
        if note:
            fixes.append(f"{name}: {note}")

    # 총 내용량 숫자가 열량과 같고 기준량과 다르면 열량을 옮겨 적은 것으로 본다
    calories, _ = parse_nutrient(parsed.get("calories"), "kcal")
    basis, total = amount_number(cleaned, "basis"), amount_number(cleaned, "total")
    if total is not None and basis is not None and total != basis and total == calories:
        fixes.append(f"총 내용량: 열량과 같은 값 제외({total:g})")
        cleaned["total_amount"], cleaned["total_unit"] = None, None
    return cleaned, fixes


# ========================================================
# 3. 값 검증과 결과 구성
# ========================================================
def check_label_values(label):
    flags = []
    if label["sugar"] is not None and label["carbs"] is not None and label["sugar"] > label["carbs"]:
        flags.append(f"당류({label['sugar']:g}g)가 탄수화물({label['carbs']:g}g)보다 큼")
    if label["sodium"] is not None and label["sodium"] > MAX_PLAUSIBLE_SODIUM_MG:
        flags.append(f"나트륨이 비정상적으로 큼({label['sodium']:g}mg)")

    values = [label[key] for key in ("calories", "carbs", "protein", "fat")]
    if all(value is not None for value in values) and label["calories"] > 0:
        estimated = 4 * label["carbs"] + 4 * label["protein"] + 9 * label["fat"]
        diff = abs(estimated - label["calories"]) / label["calories"]
        if diff > CALORIE_DIFF_THRESHOLD:
            flags.append(f"표기 열량 {label['calories']:g}kcal와 계산 열량 {estimated:g}kcal의 차이가 큼")
    return flags


def percent_flags(parsed):
    """적힌 양으로 계산한 1일 기준치 비율이 라벨의 %와 맞는지 확인한다."""
    flags = []
    for key, daily in DAILY_VALUES.items():
        value, _ = parse_nutrient(parsed.get(key), CHECK_UNITS[key])
        percent = parse_percent(parsed.get(f"{key}_pct"))
        if value is None or percent is None:
            continue
        expected = value / daily * 100
        if abs(expected - percent) > max(PERCENT_TOLERANCE, percent * 0.1):
            flags.append(f"{CHECK_NAMES[key]} {value:g}{CHECK_UNITS[key]}의 계산 비율 {expected:.0f}%가 라벨 {percent:g}%와 다름")
    return flags


def amount_flags(cleaned, result):
    """포장 양을 믿을 수 없는 경우를 찾는다."""
    flags = []
    # fill_amounts는 해석하지 못한 값을 빈 값으로 보고 덮어쓰므로 여기서 잡는다
    for key, name in (("basis", "기준량"), ("total", "총 내용량")):
        problem = parse_amount(cleaned.get(f"{key}_amount"), cleaned.get(f"{key}_unit"))[2]
        if problem and f"{name}: {problem}" not in result["flags"]:
            flags.append(f"{name}: {problem}")

    calories, _ = parse_nutrient(cleaned.get("calories"), "kcal")
    basis, total = amount_number(cleaned, "basis"), amount_number(cleaned, "total")
    if total is None and basis == 100:
        flags.append("100g/100mL 기준인데 총 내용량을 알 수 없음")
    if basis is not None and total is not None and basis != total and basis == calories:
        flags.append(f"기준량 숫자가 열량과 같음({basis:g})")
    if basis is not None and total is not None and basis > total:
        flags.append(f"기준량이 총 내용량보다 큼({basis:g}>{total:g})")

    used_basis = result["basis"][0] if result["basis"] else None
    if used_basis and calories is not None and calories / used_basis > MAX_KCAL_PER_UNIT:
        flags.append(f"기준량 대비 열량이 불가능하게 큼({calories:g}kcal/{used_basis:g})")
    return flags


def empty_result(status):
    return {
        "status": status,
        "has_nutrition_table": None,
        "basis": None,
        "total": None,
        "label": {key: None for key in NUTRIENT_UNITS},
        "package": {key: None for key in NUTRIENT_UNITS},
        "flags": [],
        "amount_fixes": [],
    }


def build_result(output_text):
    """모델 출력을 검증하고, 포장 1개 기준 수치는 코드로 계산한다."""
    parsed = extract_json(output_text)
    if parsed is None:
        return empty_result("JSON 파싱 실패")

    result = empty_result("OK")
    flags = result["flags"]
    cleaned, result["amount_fixes"] = clean_amounts(parsed)
    filled = fill_amounts(cleaned)

    has_table = filled.get("has_nutrition_table")
    result["has_nutrition_table"] = has_table
    if has_table is False:
        result["status"] = "영양표 없음"
        if any(parse_value(filled.get(key))[0] is not None for key in NUTRIENT_UNITS):
            flags.append("영양표 없음으로 판단했으나 수치를 출력해 폐기함")
        return result
    if has_table is not True:
        flags.append(f"영양표 여부 불명확({has_table})")

    for key, unit in NUTRIENT_UNITS.items():
        number, problem = parse_nutrient(filled.get(key), unit)
        result["label"][key] = number
        if problem:
            flags.append(f"{NUTRIENT_LABELS[key]}: {problem}")
        elif number is None:
            flags.append(f"{NUTRIENT_LABELS[key]}: 값 없음")

    basis_amount, basis_unit, basis_problem = parse_amount(filled.get("basis_amount"), filled.get("basis_unit"))
    total_amount, total_unit, total_problem = parse_amount(filled.get("total_amount"), filled.get("total_unit"))
    result["basis"] = (basis_amount, basis_unit) if basis_amount is not None else None
    result["total"] = (total_amount, total_unit) if total_amount is not None else None

    if basis_problem:
        flags.append(f"기준량: {basis_problem}")
    if total_problem:
        flags.append(f"총 내용량: {total_problem}")

    if basis_amount is None or total_amount is None:
        flags.append("기준량 또는 총 내용량이 없어 포장 1개 환산 불가")
    elif basis_unit != total_unit:
        flags.append(f"기준량과 총 내용량의 단위가 달라 환산 불가({basis_unit}, {total_unit})")
    elif basis_amount <= 0:
        flags.append(f"기준량 값 이상({basis_amount})")
    else:
        factor = total_amount / basis_amount
        for key, number in result["label"].items():
            if number is not None:
                result["package"][key] = round(number * factor, 2)

    flags.extend(check_label_values(result["label"]))

    saturated_fat, _ = parse_nutrient(filled.get("saturated_fat"), "g")
    if saturated_fat is not None:
        fat, protein = result["label"]["fat"], result["label"]["protein"]
        if fat is not None and saturated_fat > fat:
            flags.append(f"포화지방({saturated_fat:g}g)이 지방({fat:g}g)보다 큼")
        if protein is not None and saturated_fat > 0 and protein == saturated_fat:
            flags.append(f"단백질과 포화지방 값이 같음({protein:g}g)")

    flags.extend(percent_flags(filled))
    flags.extend(amount_flags(cleaned, result))
    return result


def classify_result(result, product_name=None):
    """DB 포함 기준: 6개 성분이 모두 있고 검증에서 걸린 내용이 없어야 한다."""
    if result["status"] in ("JSON 파싱 실패", "추론 실패"):
        return OUTCOME_FAILED
    if result["status"] == "영양표 없음":
        return OUTCOME_NO_TABLE
    if any(value is None for value in result["label"].values()):
        return OUTCOME_MISSING
    if not result["flags"] and product_name in EXCLUDED_PRODUCTS:
        result["flags"].append(EXCLUDED_FLAG)
    return OUTCOME_REVIEW if result["flags"] else OUTCOME_OK


# ========================================================
# 4. 모델 추론
# ========================================================
def load_model(load_in_4bit=False):
    global model, processor

    # 저장된 결과만 다룰 때는 GPU 라이브러리가 필요 없도록 여기서 불러온다
    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration

    options = {"device_map": "auto"}
    if load_in_4bit:
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
    else:
        options["dtype"] = torch.bfloat16

    print(f"{MODEL_ID} 로딩 중 ({'4-bit' if load_in_4bit else 'bf16'})...", flush=True)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL_ID, **options)
    processor = AutoProcessor.from_pretrained(MODEL_ID)


def analyze_single_image(image_path, max_pixels):
    import torch
    from qwen_vl_utils import process_vision_info

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": str(image_path), "min_pixels": MIN_PIXELS, "max_pixels": max_pixels},
                {"type": "text", "text": USER_PROMPT},
            ],
        },
    ]
    text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages, image_patch_size=PATCH_SIZE)
    # process_vision_info가 이미 크기를 맞추므로 프로세서에서 다시 줄이지 않는다
    inputs = processor(
        text=[text_prompt],
        images=image_inputs,
        videos=video_inputs,
        do_resize=False,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
    trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0].strip()


# ========================================================
# 5. 입력 데이터
# ========================================================
def find_base_output_dir():
    candidates = [
        Path.cwd() / "cu_data" / "cu_output",
        Path.cwd() / "cu_output",
        Path(__file__).resolve().parent / "cu_data" / "cu_output",
        Path(__file__).resolve().parent / "cu_output",
    ]
    for candidate in candidates:
        if (candidate / "categories").exists():
            return candidate
    raise SystemExit("cu_output 폴더를 찾지 못했습니다. --base-dir로 지정해 주세요.")


def image_names(image_files):
    """저장된 경로는 다른 PC에서 다를 수 있어 파일명만 사용한다."""
    return image_files.str.replace("\\", "/", regex=False).str.split("/").str[-1]


def load_category_items(base_dir, category_name):
    """이미지가 실제로 있는 상품만 읽는다. 같은 이미지를 쓰는 상품은 한 번만 처리한다."""
    csv_path = base_dir / "categories" / category_name / "products.csv"
    img_dir = base_dir / "images" / category_name
    if not csv_path.exists():
        print(f"[오류] products.csv 파일이 없습니다: {csv_path}")
        return []

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df["_image"] = image_names(df["image_files"])
    items = {}
    for _, row in df.iterrows():
        image_path = img_dir / row["_image"]
        if not row["_image"] or not image_path.exists():
            continue
        items.setdefault(row["_image"], {
            "category": category_name,
            "product_name": row["product_name"],
            "price": row["price"],
            "image_path": image_path,
        })
    return [items[name] for name in sorted(items)]


# ========================================================
# 6. 추론 결과 저장
# ========================================================
def to_result_row(item, outcome, result, elapsed, raw_output):
    basis = result["basis"] or (None, None)
    total = result["total"] or (None, None)
    return [
        item["category"], item["product_name"], item["price"], item["image_path"].name,
        outcome, result["status"], result["has_nutrition_table"],
        basis[0], basis[1], total[0], total[1],
        *[result["label"][key] for key in RESULT_VALUE_COLUMNS],
        *[result["package"][key] for key in RESULT_VALUE_COLUMNS],
        "; ".join(result["flags"]), "; ".join(result["amount_fixes"]),
        f"{elapsed:.1f}", " ".join(raw_output.split()),
    ]


def process_category(base_dir, results_dir, category, limit, max_pixels):
    import torch

    output_path = results_dir / f"{category}{RESULT_SUFFIX}"
    items = load_category_items(base_dir, category)
    done = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8-sig", newline="") as f:
            done = {row["image"] for row in csv.DictReader(f)}
    pending = [item for item in items if item["image_path"].name not in done]
    if limit is not None:
        pending = pending[:limit]
    print(f"{category}: 전체 {len(items)}건, 이번 처리 {len(pending)}건", flush=True)

    counts = Counter()
    is_new = not output_path.exists()
    with output_path.open("a", encoding="utf-8-sig" if is_new else "utf-8", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(RESULT_COLUMNS)
        for index, item in enumerate(pending, 1):
            started = time.perf_counter()
            try:
                raw_output = analyze_single_image(item["image_path"], max_pixels)
                result = build_result(raw_output)
            except Exception as e:
                torch.cuda.empty_cache()
                raw_output = f"ERROR: {e}"
                result = empty_result("추론 실패")
            outcome = classify_result(result, item["product_name"])
            writer.writerow(to_result_row(item, outcome, result, time.perf_counter() - started, raw_output))
            f.flush()
            counts[outcome] += 1
            if index % 50 == 0:
                print(f"{category} {index}/{len(pending)} {dict(counts)}", flush=True)
    print(f"{category} 완료 {dict(counts)}", flush=True)


# ========================================================
# 7. products.csv 반영
# ========================================================
def serialize_csv(df):
    return df.to_csv(index=False, encoding="utf-8-sig", lineterminator="\r\n").encode("utf-8-sig")


def apply_results(base_dir, results_dir, category):
    """DB 포함 상품의 라벨 값을 products.csv의 영양소 컬럼에 넣고, 그 외 행은 비워 둔다."""
    csv_path = base_dir / "categories" / category / "products.csv"
    result_path = results_dir / f"{category}{RESULT_SUFFIX}"
    backup_path = csv_path.with_name("products.csv.before_vlm.bak")

    original = csv_path.read_bytes()
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    results = pd.read_csv(result_path, dtype=str, keep_default_na=False)
    if results["image"].duplicated().any():
        raise SystemExit(f"결과에 중복 이미지가 있어 중단: {result_path}")

    base_columns = [column for column in df.columns if column not in RESULT_VALUE_COLUMNS]
    # 다시 저장했을 때 기존 내용이 바뀌는 파일에는 쓰지 않는다
    if serialize_csv(df) != original:
        raise SystemExit(f"다시 저장하면 기존 내용이 바뀌어 중단: {csv_path}")

    accepted = results[results["outcome"] == OUTCOME_OK].set_index("image")
    names = image_names(df["image_files"])
    matched = names.isin(accepted.index) & names.ne("")
    missing = set(accepted.index) - set(names)
    if missing:
        raise SystemExit(f"{category}: products.csv에 없는 결과 이미지 {len(missing)}건")

    updated = df[base_columns].copy()
    for key, column in RESULT_VALUE_COLUMNS.items():
        updated[key] = [
            f"{float(accepted.at[name, column]):g}" if is_match else ""
            for name, is_match in zip(names, matched)
        ]
    if serialize_csv(updated[base_columns]) != serialize_csv(df[base_columns]):
        raise SystemExit(f"기존 컬럼이 바뀌어 중단: {csv_path}")

    if not backup_path.exists():
        shutil.copy2(csv_path, backup_path)
    temp_path = csv_path.with_name("products.csv.tmp")
    temp_path.write_bytes(serialize_csv(updated))
    temp_path.replace(csv_path)
    print(f"{category}: {len(updated)}행 중 {int(matched.sum())}행 반영 (백업 {backup_path.name})", flush=True)


# ========================================================
# 8. 코드 점검 (모델 불필요)
# ========================================================
def self_check():
    good = {
        "has_nutrition_table": True, "basis_amount": "163g", "basis_unit": "g", "total_amount": "163g", "total_unit": "g",
        "calories": "252kcal", "sodium": "820 mg", "sodium_pct": "41%", "carbs": 47, "carbs_pct": 15, "sugar": 7, "sugar_pct": "7 %",
        "fat": 4.4, "fat_pct": 8, "trans_fat": 0, "saturated_fat": 1.6, "saturated_fat_pct": 11,
        "cholesterol": 5, "cholesterol_pct": 2, "protein": 6, "protein_pct": 11,
    }

    def run(**changes):
        return build_result(json.dumps({**good, **changes}, ensure_ascii=False))

    def outcome(**changes):
        return classify_result(run(**changes))

    assert run()["flags"] == [] and run()["amount_fixes"] == []
    assert outcome() == OUTCOME_OK
    # % 기호가 붙어도 오류를 잡는다
    assert any("단백질" in flag for flag in run(protein=1.6, protein_pct="11%")["flags"])
    assert any("당류" in flag for flag in run(sugar=1.3, sugar_pct="0%")["flags"])
    assert percent_flags({"sodium": 3990, "sodium_pct": 200}) == []  # 큰 값의 반올림은 허용
    # 한쪽만 있으면 복사한다
    assert run(basis_amount=None, basis_unit=None)["basis"] == (163.0, "g")
    assert run(total_amount=None, total_unit=None)["total"] == (163.0, "g")
    # '1g 미만'은 숫자로 옮기지 않는다
    assert outcome(protein="1g 미만", protein_pct=1) == OUTCOME_MISSING
    # 영양표가 없으면 값을 버린다
    no_table = run(has_nutrition_table=False)
    assert classify_result(no_table) == OUTCOME_NO_TABLE and no_table["label"]["calories"] is None
    # 총 내용량 칸의 열량을 양으로 쓰지 않는다
    for total in ("252kcal", "252 Kcal"):
        result = run(total_amount=total, total_unit="kcal")
        assert result["flags"] == [] and result["total"] == (163.0, "g") and result["package"]["calories"] == 252
    # 괄호와 머리글이 붙은 표기를 정리한다
    result = run(basis_amount="1개(163g)당", total_amount="총 내용량 163 g (252 kcal)")
    assert result["flags"] == [] and result["basis"] == (163.0, "g") and result["total"] == (163.0, "g")
    # 기준량에 열량이 들어가면 총 내용량을 쓴다
    result = run(basis_amount="252Kcal", basis_unit="kcal")
    assert result["flags"] == [] and result["basis"] == (163.0, "g")
    # 총 내용량 숫자가 열량과 같으면 버린다
    result = run(total_amount="252", total_unit="g")
    assert result["flags"] == [] and result["total"] == (163.0, "g")
    # 100g 기준에서 총 내용량을 모르면 보류한다
    assert outcome(basis_amount="100g", total_amount="252kcal", total_unit="kcal") == OUTCOME_REVIEW
    assert outcome(basis_amount="100g", total_amount=None, total_unit=None) == OUTCOME_REVIEW
    # 총 내용량이 있으면 환산한다
    result = run(basis_amount="100g", total_amount="200g")
    assert result["flags"] == [] and result["package"]["calories"] == 504
    # 믿을 수 없는 양은 보류한다
    assert outcome(basis_amount="252g", total_amount="500g") == OUTCOME_REVIEW  # 기준량이 열량과 같음
    assert outcome(basis_amount="755g", total_amount="255g") == OUTCOME_REVIEW  # 기준량이 총량보다 큼
    assert outcome(total_amount="100g당 300g") == OUTCOME_REVIEW  # g 값이 둘
    assert outcome(basis_amount="20g", total_amount="20g") == OUTCOME_REVIEW  # 불가능한 열량 밀도
    # mg이나 kcal을 g으로 읽지 않는다
    assert AMOUNT_RE.findall("190kcal") == [] and AMOUNT_RE.findall("5mg") == []
    # 제외 상품은 DB에 넣지 않는다
    excluded = next(iter(EXCLUDED_PRODUCTS))
    assert classify_result(run(), excluded) == OUTCOME_REVIEW
    # JSON이 아니면 실패로 처리한다
    assert classify_result(build_result("표를 찾을 수 없습니다")) == OUTCOME_FAILED
    print("self check passed", flush=True)


# ========================================================
# 9. 실행
# ========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="CU 영양성분표 이미지에서 영양소를 추출한다.")
    parser.add_argument("--categories", nargs="+", default=CATEGORIES_TO_PROCESS, help="처리할 카테고리")
    parser.add_argument("--limit", type=int, help="카테고리별 이번 처리 건수 (시험용)")
    parser.add_argument("--base-dir", type=Path, help="cu_output 폴더")
    parser.add_argument("--results-dir", type=Path, help=f"결과 CSV 폴더 (기본값: cu_output/{RESULT_DIR_NAME})")
    parser.add_argument("--load-in-4bit", action="store_true", help="8GB GPU용 4-bit 양자화")
    parser.add_argument("--apply", action="store_true", help="추론 후 products.csv에 반영")
    parser.add_argument("--apply-only", action="store_true", help="추론 없이 저장된 결과를 products.csv에 반영")
    parser.add_argument("--self-check", action="store_true", help="모델 없이 검증 코드만 점검")
    return parser.parse_args()


def main():
    args = parse_args()
    self_check()
    if args.self_check:
        return

    base_dir = args.base_dir or find_base_output_dir()
    results_dir = args.results_dir or base_dir / RESULT_DIR_NAME
    results_dir.mkdir(parents=True, exist_ok=True)

    if not args.apply_only:
        load_model(args.load_in_4bit)
        max_pixels = MAX_PIXELS_4BIT if args.load_in_4bit else MAX_PIXELS
        started = time.perf_counter()
        for category in args.categories:
            process_category(base_dir, results_dir, category, args.limit, max_pixels)
        print(f"추론 완료 {(time.perf_counter() - started) / 3600:.2f}시간", flush=True)

    if args.apply or args.apply_only:
        for category in args.categories:
            apply_results(base_dir, results_dir, category)


if __name__ == "__main__":
    main()
