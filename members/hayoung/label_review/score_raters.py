"""Step 1: compare blind rater sheets with the labels and with each other. Order-free pairs.

usage: python score_raters.py blind_key_DO_NOT_SHARE.csv 조혁준.xlsx 이규남.xlsx ...
"""
import collections
import csv
import itertools
import os
import sys

from openpyxl import load_workbook


def read_rater(path):
    answers = {}
    for row in load_workbook(path, read_only=True)["라벨링"].iter_rows(min_row=2, values_only=True):
        num, _, a, ad, b, bd = row[:6]
        answers[int(num)] = frozenset({(a, ad), (b, bd)}) if all((a, ad, b, bd)) else None
    return answers


def read_key(path):
    key = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        key[int(r["번호"])] = (r["상황ID"], frozenset({(r["성분1"], r["방향1"]), (r["성분2"], r["방향2"])}))
    return key


def agreement(a, b):
    nums = [n for n in a if a[n] is not None and b.get(n) is not None]
    return sum(a[n] == b[n] for n in nums), len(nums)


def main(key_path, rater_paths):
    key = read_key(key_path)
    gold = {n: v[1] for n, v in key.items()}
    raters = {os.path.splitext(os.path.basename(p))[0]: read_rater(p) for p in rater_paths}
    print(f"문장 {len(key)}개")
    for name, ans in raters.items():
        ok, n = agreement(ans, gold)
        blank = sum(ans.get(i) is None for i in key)
        print(f"[라벨과 일치] {name}: {ok}/{n} = {ok/n:.1%}" if n else f"[라벨과 일치] {name}: 답 없음", f"(미응답 {blank})")
    for (x, a), (y, b) in itertools.combinations(raters.items(), 2):
        ok, n = agreement(a, b)
        print(f"[평가자끼리 일치] {x} - {y}: {ok}/{n} = {ok/n:.1%}" if n else f"[평가자끼리 일치] {x} - {y}: 답 없음")
    per = collections.defaultdict(lambda: [0, 0])
    for name, ans in raters.items():
        for num, (sit, g) in key.items():
            if ans.get(num) is not None:
                per[sit][0] += ans[num] == g
                per[sit][1] += 1
    print("[상황별 라벨 일치 (평가자 합산)]")
    for sit, (ok, n) in sorted(per.items()):
        print(f"  {sit}: {ok}/{n}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
