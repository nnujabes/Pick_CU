"""Step 3: validate a filled augmentation sheet and write a NEW merged train file.

The originals are never changed. Writes the output only if every check passes.
usage: python check_augment.py <filled_csv> <train_csv> <dev_csv> <out_csv>
"""
import csv
import difflib
import sys

NUTRIENTS = {"열량", "단백질", "나트륨", "탄수화물", "당류", "지방"}
DIRECTIONS = {"높음", "낮음"}
MAX_DEV_SIMILARITY = 0.8
TRAIN_COLUMNS = ["상황ID", "입력 문장", "말투 유형", "작성자", "성분1", "방향1", "성분2", "방향2"]


def read(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def check(new, train, dev):
    problems = []
    train_ids = {r["상황ID"] for r in train}
    dev_ids = {r["상황ID"] for r in dev}
    existing = {r["입력 문장"].strip() for r in train} | {r["입력 문장"].strip() for r in dev}
    dev_sents = [r["입력 문장"] for r in dev]
    seen = set()
    labels = {}
    for i, r in enumerate(new, 2):
        s = (r["입력 문장"] or "").strip()
        if not s:
            problems.append(f"{i}행: 문장이 비어 있음")
            continue
        if not (r["작성자"] or "").strip():
            problems.append(f"{i}행: 작성자가 비어 있음")
        if r["상황ID"] in train_ids | dev_ids:
            problems.append(f"{i}행: 기존 상황ID와 겹침 ({r['상황ID']})")
        if r["성분1"] not in NUTRIENTS or r["성분2"] not in NUTRIENTS:
            problems.append(f"{i}행: 성분 값 오류 ({r['성분1']}, {r['성분2']})")
        if r["방향1"] not in DIRECTIONS or r["방향2"] not in DIRECTIONS:
            problems.append(f"{i}행: 방향 값 오류 ({r['방향1']}, {r['방향2']})")
        if r["성분1"] == r["성분2"]:
            problems.append(f"{i}행: 성분1과 성분2가 같음")
        if s in existing or s in seen:
            problems.append(f"{i}행: 중복 문장 ({s})")
        seen.add(s)
        label = (r["성분1"], r["방향1"], r["성분2"], r["방향2"])
        if labels.setdefault(r["상황ID"], label) != label:
            problems.append(f"{i}행: 같은 상황 안에서 라벨이 다름 ({r['상황ID']})")
        best = max(dev_sents, key=lambda d: difflib.SequenceMatcher(None, s, d).ratio())
        sim = difflib.SequenceMatcher(None, s, best).ratio()
        if sim >= MAX_DEV_SIMILARITY:
            problems.append(f"{i}행: dev 문장과 너무 비슷함 ({sim:.2f}): {s} / {best}")
    return problems


def main(new_path, train_path, dev_path, out_path):
    new, train, dev = read(new_path), read(train_path), read(dev_path)
    problems = check(new, train, dev)
    if problems:
        print(f"문제 {len(problems)}건, 파일을 만들지 않았습니다:")
        print("\n".join(problems))
        sys.exit(1)
    with open(out_path, "x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRAIN_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(train + new)
    print(f"통과: 기존 {len(train)} + 추가 {len(new)} = {len(train) + len(new)}행, {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
