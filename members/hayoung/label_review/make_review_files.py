"""Steps 1 and 3: build the blind rater sheet and the train augmentation template.

Reads data/*_2nut.csv read-only. Writes only into label_review/.
usage: python make_review_files.py <dev_csv> <train_csv> <out_dir>
"""
import collections
import csv
import os
import random
import sys

from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

SEED = 42
PER_SITUATION = 5
NUTRIENTS = ["열량", "단백질", "나트륨", "탄수화물", "당류", "지방"]
DIRECTIONS = ["높음", "낮음"]
RULES = ["운동 후 → 고단백, 저지방", "야식 → 저나트륨, 저당", "벌크업·근성장 → 고단백, 고열량",
         "마라톤·경기 전 → 고탄수화물, 저지방", "바디프로필 준비 → 저탄수화물, 고단백", "다이어트 시작 → 저열량, 저당",
         "한파·추운 날 → 고열량, 고지방", "고혈압 → 저나트륨, 저지방", "당 떨어졌을 때 → 고당류, 고탄수화물",
         "혈당 관리 → 저당, 저탄수화물"]

# Situations to add. Labels stay blank where the team has to decide them.
NEW_SITUATIONS = [
    ("S3001", "짭짤한 안주나 과자가 당길 때", "나트륨", "높음"),
    ("S3002", "입맛이 없어서 간이 센 음식을 찾을 때", "나트륨", "높음"),
    ("S3003", "라면이나 국물처럼 짠 국물이 당길 때", "나트륨", "높음"),
    ("S3004", "온종일 야외 활동 후 염분을 보충하고 싶을 때", "나트륨", "높음"),
    ("S3005", "맵고 짠 자극적인 음식이 먹고 싶을 때", "나트륨", "높음"),
    ("S3006", "단백질 섭취를 제한해야 하는 식단일 때", "단백질", "낮음"),
]


def read(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def blind_sheet(dev, out_dir):
    rng = random.Random(SEED)
    by_sit = collections.defaultdict(list)
    for r in dev:
        by_sit[r["상황ID"]].append(r)
    picked = [r for sit in sorted(by_sit) for r in rng.sample(by_sit[sit], PER_SITUATION)]
    rng.shuffle(picked)

    wb = Workbook()
    guide = wb.active
    guide.title = "안내"
    lines = ["문장만 보고 필요한 영양소 2개와 방향을 고르세요. 순서는 상관없습니다.",
             "다른 사람과 상의하지 말고, 정답 파일이나 이전 결과를 보지 말고 혼자 작성하세요.",
             "확신이 없어도 가장 맞다고 생각하는 답을 고르세요.", "", "참고 규칙 (모델에게 주는 것과 같습니다):"]
    for line in lines + [f"{i}. {x}" for i, x in enumerate(RULES, 1)]:
        guide.append([line])
    guide.column_dimensions["A"].width = 80

    ws = wb.create_sheet("라벨링")
    ws.append(["번호", "입력 문장", "영양소A", "방향A", "영양소B", "방향B"])
    for i, r in enumerate(picked, 1):
        ws.append([i, r["입력 문장"]])
    for col, values in (("C", NUTRIENTS), ("D", DIRECTIONS), ("E", NUTRIENTS), ("F", DIRECTIONS)):
        dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True, showErrorMessage=True)
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{len(picked) + 1}")
    ws.column_dimensions["B"].width = 90
    wb.save(os.path.join(out_dir, "blind_label_sheet.xlsx"))

    with open(os.path.join(out_dir, "blind_key_DO_NOT_SHARE.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["번호", "상황ID", "입력 문장", "성분1", "방향1", "성분2", "방향2"])
        for i, r in enumerate(picked, 1):
            w.writerow([i, r["상황ID"], r["입력 문장"], r["성분1"], r["방향1"], r["성분2"], r["방향2"]])
    return len(picked)


def augment_template(train, out_dir):
    """One row per sentence slot, using the 말투 유형 mix most common among train situations."""
    by_sit = collections.defaultdict(collections.Counter)
    for r in train:
        by_sit[r["상황ID"]][r["말투 유형"]] += 1
    mix = collections.Counter(tuple(sorted(c.items())) for c in by_sit.values()).most_common(1)[0][0]
    rows = 0
    with open(os.path.join(out_dir, "train_augment_template.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["상황ID", "상황 설명", "입력 문장", "말투 유형", "작성자", "성분1", "방향1", "성분2", "방향2"])
        for sid, desc, nut, d in NEW_SITUATIONS:
            for style, n in mix:
                for _ in range(n):
                    w.writerow([sid, desc, "", style, "", nut, d, "", ""])
                    rows += 1
    return rows, dict(mix)


def main(dev_path, train_path, out_dir):
    n = blind_sheet(read(dev_path), out_dir)
    rows, mix = augment_template(read(train_path), out_dir)
    print(f"blind sheet: {n} sentences; augment template: {rows} rows; style mix per situation: {mix}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
