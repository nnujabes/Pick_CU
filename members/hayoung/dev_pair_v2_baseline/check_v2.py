"""0단계 데이터 검사: dev_pair_v2.csv, train_pair_v2.csv (읽기 전용).
usage: python check_v2.py <dev_csv> <train_csv> <out_json>
하나라도 실패하면 exit 1.
"""
import collections
import csv
import hashlib
import json
import sys

COLS = ["상황ID", "입력 문장", "말투 유형", "작성자", "성분1", "방향1", "성분2", "방향2"]
PAIR = {("단백질", "높음"): ("지방", "낮음"), ("단백질", "낮음"): ("나트륨", "낮음"),
        ("나트륨", "낮음"): ("지방", "낮음"), ("나트륨", "높음"): ("당류", "높음"),
        ("열량", "높음"): ("탄수화물", "높음"), ("열량", "낮음"): ("지방", "낮음"),
        ("탄수화물", "높음"): ("열량", "높음"), ("탄수화물", "낮음"): ("단백질", "높음"),
        ("당류", "높음"): ("열량", "높음"), ("당류", "낮음"): ("열량", "낮음"),
        ("지방", "높음"): ("열량", "높음"), ("지방", "낮음"): ("열량", "낮음")}
RULE_SITS = ["S001", "S019", "S2014", "S2046", "S2042", "S2001", "S2056", "S2065", "S2024", "S2030"]


def load(path):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8")  # UTF-8이 아니면 여기서 실패
    rows = list(csv.reader(text.lstrip("﻿").splitlines()))
    header, body = rows[0], rows[1:]
    blank = sum(1 for r in body if not any(c.strip() for c in r))
    recs = [dict(zip(header, r)) for r in body if any(c.strip() for c in r)]
    return header, recs, blank, hashlib.md5(raw).hexdigest(), raw.startswith(b"\xef\xbb\xbf")


def main(dev_p, train_p, out_p):
    res = {"files": {}, "checks": {}}
    data = {}
    for name, p in (("dev", dev_p), ("train", train_p)):
        h, recs, blank, md5, bom = load(p)
        data[name] = recs
        res["files"][name] = {"path": p, "md5": md5, "rows": len(recs), "blank_rows": blank, "utf8_bom": bom,
                              "header": h, "situations": len({r["상황ID"] for r in recs})}
    d, t = data["dev"], data["train"]
    C = res["checks"]

    def add(key, ok, detail):
        C[key] = {"ok": bool(ok), "detail": detail}

    add("1_utf8_and_columns", all(res["files"][n]["header"] == COLS for n in data),
        {n: res["files"][n]["header"] for n in data})
    add("2_counts", len(d) == 216 and res["files"]["dev"]["situations"] == 12
        and len(t) == 2820 and res["files"]["train"]["situations"] == 94,
        {n: [res["files"][n]["rows"], res["files"][n]["situations"]] for n in data})
    sit_overlap = sorted({r["상황ID"] for r in d} & {r["상황ID"] for r in t})
    sent_overlap = sorted({r["입력 문장"].strip() for r in d} & {r["입력 문장"].strip() for r in t})
    dup = {n: [s for s, c in collections.Counter(r["입력 문장"].strip() for r in data[n]).items() if c > 1]
           for n in data}
    add("3_no_overlap_no_dup", not sit_overlap and not sent_overlap and not dup["dev"] and not dup["train"],
        {"situation_overlap": sit_overlap, "sentence_overlap": sent_overlap, "dup_within": dup})
    multi = {}
    for n in data:
        g = collections.defaultdict(set)
        for r in data[n]:
            g[r["상황ID"]].add((r["성분1"], r["방향1"]))
        multi[n] = {k: sorted(v) for k, v in g.items() if len(v) != 1}
    add("4_one_first_per_situation", not multi["dev"] and not multi["train"], multi)
    bad = {n: [(r["상황ID"], r["성분1"], r["방향1"], r["성분2"], r["방향2"]) for r in data[n]
               if PAIR.get((r["성분1"], r["방향1"])) != (r["성분2"], r["방향2"])] for n in data}
    add("5_pair_table", not bad["dev"] and not bad["train"],
        {n: {"mismatch_rows": len(bad[n]), "examples": sorted(set(bad[n]))[:10]} for n in data})
    tr_s, dv_s = {r["상황ID"] for r in t}, {r["상황ID"] for r in d}
    add("6_rule_situations_train_only",
        all(s in tr_s for s in RULE_SITS) and not any(s in dv_s for s in RULE_SITS),
        {"missing_in_train": [s for s in RULE_SITS if s not in tr_s], "present_in_dev": [s for s in RULE_SITS if s in dv_s]})
    na_tr = sorted({r["상황ID"] for r in t if (r["성분1"], r["방향1"]) == ("나트륨", "높음")})
    na_dv = sorted({r["상황ID"] for r in d if (r["성분1"], r["방향1"]) == ("나트륨", "높음")})
    add("7_sodium_high", na_tr == ["S037", "S038", "S039", "S040"] and "S041" in na_dv,
        {"train": na_tr, "dev": na_dv})
    add("8_md5_rows", True, {n: {"md5": res["files"][n]["md5"], "rows": res["files"][n]["rows"]} for n in data})

    res["dev_situations"] = {k: f"{v[0]}{v[1]}+{v[2]}{v[3]} ({c}문장)" for (k, *v), c in sorted(collections.Counter(
        (r["상황ID"], r["성분1"], r["방향1"], r["성분2"], r["방향2"]) for r in d).items())}
    res["all_ok"] = all(v["ok"] for v in C.values())
    json.dump(res, open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for k, v in C.items():
        print(("PASS " if v["ok"] else "FAIL ") + k, json.dumps(v["detail"], ensure_ascii=False)[:400])
    print("dev 상황:", json.dumps(res["dev_situations"], ensure_ascii=False))
    print("ALL_OK" if res["all_ok"] else "CHECK_FAILED")
    sys.exit(0 if res["all_ok"] else 1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
