"""reproduce_all.sh 결과를 저장된 원래 결과와 비교한다.
- 모델 출력(raw_output)이 문장마다 똑같은지, 정답 수가 같은지
- 파인튜닝 데이터(jsonl)가 원래 학습에 쓴 파일과 md5가 같은지
- 학습 흐름 점검(smoke)이 끝까지 돌았는지

usage: python compare_repro.py <repro_out>
"""
import csv
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 원래 학습(서버 166, 2026-11-04)에 쓴 jsonl의 md5
FT_DATA_MD5 = {"train_sft.jsonl": "ed49b455629207c969219f68655cfcd5", "val_sft.jsonl": "628497f5ff861efa6406cf11cc6eb3e0",
               "split_info.csv": "97ec28365062cadab5746cdc7a1d4283"}
PAIRS = [  # (이름, 원래 rows, 새 rows, 정답 열, 정답 값)
    ("dev_baseline (1성분)", "dev_baseline/dev_baseline_rows.csv", "dev_baseline/dev_baseline_rows.csv", "both_ok", "1"),
    ("dev_2nut_baseline", "dev_2nut_baseline/rows.csv", "dev_2nut_baseline/rows.csv", "결과", None),
    ("dev_pair_baseline", "dev_pair_baseline/rows.csv", "dev_pair_baseline/rows.csv", "결과", None),
    ("dev_pair_v2_baseline", "dev_pair_v2_baseline/rows.csv", "dev_pair_v2_baseline/rows.csv", "결과", None),
    ("dev_pair_v3_baseline", "dev_pair_v3_baseline/rows.csv", "dev_pair_v3_baseline/rows.csv", "결과", None),
    ("파인튜닝 best (dev)", "ft_ax_v1/results/run_r16_lr2e-4/dev_best/rows.csv", "ft_dev_best/rows.csv", "결과", None),
]


def read(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def n_correct(rows, col, val):
    if val is not None:
        return sum(r[col] in (val, "True") for r in rows)
    return sum(r[col] == rows_ok_value(rows, col) for r in rows)


def rows_ok_value(rows, col):
    # '결과' 열은 맞음/틀림 표기
    vals = {r[col] for r in rows}
    for v in ("맞음", "O", "정답", "1", "True"):
        if v in vals:
            return v
    return None


def main(out):
    ok_all, lines = True, []
    for name, orig, new, col, val in PAIRS:
        po, pn = os.path.join(HERE, orig), os.path.join(out, new)
        if not os.path.exists(pn):
            lines.append(f"[없음] {name}: {pn}")
            ok_all = False
            continue
        a, b = read(po), read(pn)
        same_n = len(a) == len(b)
        diff = [i + 1 for i, (x, y) in enumerate(zip(a, b)) if x["raw_output"] != y["raw_output"] or x["입력 문장"] != y["입력 문장"]]
        ca, cb = n_correct(a, col, val), n_correct(b, col, val)
        ok = same_n and not diff and ca == cb
        ok_all &= ok
        lines.append(f"[{'같음' if ok else '다름'}] {name}: 정답 원래 {ca}/{len(a)} / 재실행 {cb}/{len(b)}, "
                     f"출력이 다른 문장 {len(diff)}개{(' ' + str(diff[:10])) if diff else ''}")
    for f, h in FT_DATA_MD5.items():
        p = os.path.join(out, "ft_data", f)
        got = md5(p) if os.path.exists(p) else None
        ok = got == h
        ok_all &= ok
        lines.append(f"[{'같음' if ok else '다름'}] ft_data/{f}: md5 {got}")
    fs = os.path.join(out, "ft_smoke", "results", "smoke_test", "final_summary.json")
    ok = os.path.exists(fs)
    ok_all &= ok
    lines.append(f"[{'통과' if ok else '실패'}] 학습 흐름 점검(smoke): {'final_summary.json 생성됨' if ok else '결과 없음'}")
    lines.append("전체: " + ("모두 같음" if ok_all else "차이 있음"))
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(out, "compare_result.txt"), "w", encoding="utf-8").write(txt + "\n")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main(sys.argv[1])
