"""Baseline before fine-tuning: skt/A.X-4.0-Light extracts 2 (nutrient, direction) pairs per sentence.

Pair-table labels (dev_pair.csv): 성분2/방향2 follow the team's fixed pair table. This is a new reference
point; do not compare with dev_2nut_baseline. Based on dev_2nut_baseline.py, prompt replaced.

Reads dev_pair.csv only (216 rows). Only the '입력 문장' text reaches the model; gold labels are used
after generation, for scoring. bf16, official chat template, greedy, no constrained decoding, no few-shot.

usage:
  python dev_2nut_baseline.py selftest                 # scorer tests + prompt preview, no GPU
  python dev_2nut_baseline.py run <dev_csv> <out_dir>
"""
import collections
import csv
import hashlib
import json
import os
import re
import sys
import time

MODEL_ID = "skt/A.X-4.0-Light"
MODEL_REVISION = "ba21c20ea1b31ded1ec3e2fb432335077dc4be98"
MAX_NEW_TOKENS = 128
SEED = 42

NUT_MAP = {"열량": "calories", "단백질": "protein", "나트륨": "sodium", "탄수화물": "carbs", "당류": "sugar", "지방": "fat"}
DIR_MAP = {"높음": "high", "낮음": "low"}
NUTRIENTS = ["calories", "protein", "sodium", "carbs", "sugar", "fat"]
DIRECTIONS = ["high", "low"]

SYSTEM_PROMPT = """당신은 편의점 영양 추천 도우미입니다. 사용자 문장을 보고 필요한 영양소 2개와 방향(높음/낮음)을 JSON으로만 답하세요.

출력 형식: {"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "fat", "direction": "low"}]}
성분: calories, protein, sodium, carbs, sugar, fat
방향: high, low
성분은 반드시 위 6개(calories, protein, sodium, carbs, sugar, fat) 중에서만 고르세요. 다른 영양소는 쓰지 마세요.

규칙 예시:
1. 운동 후 → 고단백, 저지방
2. 야식 → 저나트륨, 저지방
3. 바디프로필 준비 → 저탄수화물, 고단백
4. 다이어트 시작 → 저열량, 저지방
5. 한파·추운 날 → 고열량, 고탄수화물
6. 마라톤·경기 전 → 고탄수화물, 고열량
7. 당 떨어졌을 때 → 고당류, 고열량
8. 혈당 관리 → 저당류, 저열량
9. 크림 파스타가 당길 때 → 고지방, 고열량
10. 느끼한 음식이 물렸을 때 → 저지방, 저열량"""


def read_dev(path):
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        r["gold1"] = (NUT_MAP[r["성분1"]], DIR_MAP[r["방향1"]])
        r["gold2"] = (NUT_MAP[r["성분2"]], DIR_MAP[r["방향2"]])
        rows.append(r)
    return rows


def build_messages(sentence):
    """Takes a plain string, so no label or metadata field can reach the prompt."""
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": sentence}]


def parse_output(text):
    """Returns (items, parse_ok, schema_ok). items is a list of (nutrient, direction) strings.

    parse_ok: some JSON object was recovered. schema_ok: it has a "nutrients" list of objects.
    """
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip()).strip()
    start = t.find("{")
    if start < 0:
        return [], False, False
    try:
        obj, _ = json.JSONDecoder().raw_decode(t[start:])
    except ValueError:
        return [], False, False
    items = obj.get("nutrients") if isinstance(obj, dict) else None
    if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
        return [], True, False
    norm = lambda v: v.strip().lower() if isinstance(v, str) else ""
    return [(norm(x.get("nutrient")), norm(x.get("direction"))) for x in items], True, True


def multiset_overlap(a, b):
    return sum((collections.Counter(a) & collections.Counter(b)).values())


def score(gold1, gold2, items):
    """Order-free comparison. An exact answer must have exactly 2 items."""
    gold = {gold1, gold2}
    valid = [p for p in items if p[0] in NUTRIENTS and p[1] in DIRECTIONS]
    pred = set(valid)
    pred_nuts = [p[0] for p in items if p[0] in NUTRIENTS]
    pred_dirs = [p[1] for p in items if p[1] in DIRECTIONS]
    gold_nuts = [gold1[0], gold2[0]]
    gold_dirs = [gold1[1], gold2[1]]
    two = len(items) == 2
    s = {
        "n_items": len(items),
        "invalid_items": len(items) - len(valid),
        "same_nutrient_twice": len(pred_nuts) != len(set(pred_nuts)),
        "first_ok": gold1 in pred,
        "second_ok": gold2 in pred,
        "first_nut_ok": gold1[0] in pred_nuts,
        "second_nut_ok": gold2[0] in pred_nuts,
        "pairs_ok": len(gold & pred),
        "nuts_ok": multiset_overlap(gold_nuts, pred_nuts),
        "dirs_ok": multiset_overlap(gold_dirs, pred_dirs),
    }
    s["exact"] = two and pred == gold
    s["any_ok"] = s["pairs_ok"] >= 1
    s["nuts_exact"] = two and sorted(pred_nuts) == sorted(gold_nuts)
    s["dirs_exact"] = two and sorted(pred_dirs) == sorted(gold_dirs)
    return s


def ratio(correct, n):
    return {"correct": correct, "n": n, "acc": round(correct / n, 4) if n else None}


def overall(rows):
    n = len(rows)
    return {
        "exact": ratio(sum(r["exact"] for r in rows), n),
        "pair": ratio(sum(r["pairs_ok"] for r in rows), n * 2),
        "at_least_one": ratio(sum(r["any_ok"] for r in rows), n),
        "nutrient_only_sentence": ratio(sum(r["nuts_exact"] for r in rows), n),
        "nutrient_only_pair": ratio(sum(r["nuts_ok"] for r in rows), n * 2),
        "direction_only_sentence": ratio(sum(r["dirs_exact"] for r in rows), n),
        "direction_only_pair": ratio(sum(r["dirs_ok"] for r in rows), n * 2),
        "direction_when_nutrient_found": ratio(
            sum(r["pairs_ok"] for r in rows),
            sum(r["first_nut_ok"] + r["second_nut_ok"] for r in rows),
        ),
        "first": ratio(sum(r["first_ok"] for r in rows), n),
        "second": ratio(sum(r["second_ok"] for r in rows), n),
        "second_given_first": ratio(sum(r["first_ok"] and r["second_ok"] for r in rows),
                                    sum(r["first_ok"] for r in rows)),
    }


def by_gold_pair(rows, key_index):
    """Accuracy per gold nutrient (key_index 0) or direction (1): all gold pairs, then by position."""
    out = collections.defaultdict(lambda: {"first": [0, 0], "second": [0, 0], "nut": [0, 0]})
    for r in rows:
        for pos, gold, ok, nut_ok in (("first", r["gold1"], r["first_ok"], r["first_nut_ok"]),
                                      ("second", r["gold2"], r["second_ok"], r["second_nut_ok"])):
            k = gold[key_index]
            out[k][pos][0] += ok
            out[k][pos][1] += 1
            out[k]["nut"][0] += nut_ok
            out[k]["nut"][1] += 1
    res = {}
    for k, v in sorted(out.items()):
        res[k] = {
            "all": ratio(v["first"][0] + v["second"][0], v["first"][1] + v["second"][1]),
            "first": ratio(*v["first"]),
            "second": ratio(*v["second"]),
            "nutrient_found": ratio(*v["nut"]),
        }
    return res


def by_group(rows, field):
    g = collections.defaultdict(list)
    for r in rows:
        g[r[field]].append(r)
    return {k: {"gold": label(v[0]) if field == "상황ID" else None,
                "exact": ratio(sum(x["exact"] for x in v), len(v)),
                "pair": ratio(sum(x["pairs_ok"] for x in v), len(v) * 2),
                "first": ratio(sum(x["first_ok"] for x in v), len(v)),
                "second": ratio(sum(x["second_ok"] for x in v), len(v))}
            for k, v in sorted(g.items())}


def fmt(p):
    return f"{p[0]}/{p[1]}"


def label(r):
    return f"{fmt(r['gold1'])}, {fmt(r['gold2'])}"


def pred_label(r):
    return ", ".join(fmt(p) for p in r["items"])


def summarize(rows):
    return {
        "overall": overall(rows),
        "counts": {
            "n_items": {str(k): v for k, v in sorted(collections.Counter(r["n_items"] for r in rows).items())},
            "one_item": sum(r["n_items"] == 1 for r in rows),
            "three_or_more_items": sum(r["n_items"] >= 3 for r in rows),
            "same_nutrient_twice": sum(r["same_nutrient_twice"] for r in rows),
            "invalid_value_sentences": sum(r["invalid_items"] > 0 for r in rows),
            "invalid_values": dict(collections.Counter(
                f"{p[0]}/{p[1]}" for r in rows for p in r["items"]
                if p[0] not in NUTRIENTS or p[1] not in DIRECTIONS).most_common()),
            "parse_fail": sum(not r["parse_ok"] for r in rows),
            "schema_invalid_but_parsed": sum(r["parse_ok"] and not r["schema_ok"] for r in rows),
            "truncated_at_max_new_tokens": sum(r["truncated"] for r in rows),
        },
        "by_nutrient": by_gold_pair(rows, 0),
        "by_direction": by_gold_pair(rows, 1),
        "by_situation": by_group(rows, "상황ID"),
        "by_author": by_group(rows, "작성자"),
        "by_style": by_group(rows, "말투 유형"),
        "wrong": [{"row": r["row"], "상황ID": r["상황ID"], "입력 문장": r["입력 문장"], "정답": label(r),
                   "예측": pred_label(r), "raw_output": r["raw_output"]} for r in rows if not r["exact"]],
    }


def write_rows(rows, path, only_wrong=False):
    fields = ["row", "상황ID", "작성자", "말투 유형", "입력 문장", "정답", "예측", "결과", "맞은 쌍 수",
              "first_ok", "second_ok", "n_items", "same_nutrient_twice", "invalid_items",
              "parse_ok", "schema_ok", "truncated", "raw_output"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            if only_wrong and r["exact"]:
                continue
            w.writerow({**r, "정답": label(r), "예측": pred_label(r),
                        "결과": "맞음" if r["exact"] else "틀림", "맞은 쌍 수": r["pairs_ok"]})


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def selftest():
    g1, g2 = ("protein", "high"), ("fat", "low")
    ok = '{"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "fat", "direction": "low"}]}'
    swapped = '{"nutrients": [{"nutrient": "fat", "direction": "low"}, {"nutrient": "protein", "direction": "high"}]}'

    def sc(text):
        items, p, c = parse_output(text)
        return score(g1, g2, items), p, c

    s, p, c = sc(ok)
    assert p and c and s["exact"] and s["pairs_ok"] == 2
    assert sc(swapped)[0]["exact"]
    assert sc("```json\n" + ok + "\n```")[0]["exact"]
    assert sc("답변: " + ok + " 입니다")[0]["exact"]

    s, p, c = sc("모르겠어요")
    assert not p and not c and not s["exact"] and s["n_items"] == 0
    s, p, c = sc('{"nutrients": [{"nutrient": "protein"')
    assert not p
    s, p, c = sc('{"nutrient": "protein", "direction": "high"}')
    assert p and not c and s["pairs_ok"] == 0

    s, *_ = sc('{"nutrients": [{"nutrient": "protein", "direction": "high"}]}')
    assert s["n_items"] == 1 and not s["exact"] and s["any_ok"] and s["first_ok"] and not s["second_ok"]
    s, *_ = sc('{"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "fat", "direction": "low"},'
               ' {"nutrient": "sugar", "direction": "low"}]}')
    assert s["n_items"] == 3 and not s["exact"] and s["pairs_ok"] == 2
    s, *_ = sc('{"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "protein", "direction": "high"}]}')
    assert s["same_nutrient_twice"] and not s["exact"] and s["pairs_ok"] == 1 and s["nuts_ok"] == 1
    s, *_ = sc('{"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "protein", "direction": "low"}]}')
    assert s["same_nutrient_twice"] and not s["exact"] and s["pairs_ok"] == 1
    s, *_ = sc('{"nutrients": [{"nutrient": "단백질", "direction": "high"}, {"nutrient": "fat", "direction": "낮음"}]}')
    assert s["invalid_items"] == 2 and s["pairs_ok"] == 0
    # nutrients right, directions flipped: counts for nutrient-only, not for pairs.
    s, *_ = sc('{"nutrients": [{"nutrient": "protein", "direction": "low"}, {"nutrient": "fat", "direction": "high"}]}')
    assert s["nuts_exact"] and s["dirs_exact"] and s["pairs_ok"] == 0

    row = lambda text: {**score(g1, g2, parse_output(text)[0]), "gold1": g1, "gold2": g2}
    o = overall([row(ok), row(swapped), row("x"), row('{"nutrients": [{"nutrient": "fat", "direction": "low"}]}')])
    assert o["exact"]["correct"] == 2 and o["pair"]["correct"] == 5 and o["pair"]["n"] == 8
    assert o["first"]["correct"] == 2 and o["second"]["correct"] == 3 and o["at_least_one"]["correct"] == 3
    assert o["second_given_first"]["correct"] == 2 and o["second_given_first"]["n"] == 2
    print("selftest ok")
    print(SYSTEM_PROMPT)


def main(dev_path, out_dir):
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

    md5_before = md5(dev_path)
    dev = read_dev(dev_path)
    assert len(dev) == 216, len(dev)
    print(f"dev={len(dev)} md5={md5_before}", flush=True)

    set_seed(SEED)
    torch.backends.cudnn.deterministic = True
    tok = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, dtype=torch.bfloat16, device_map="cuda")
    model.eval()
    print(f"model loaded, GPU mem {torch.cuda.memory_allocated()/2**30:.1f} GiB", flush=True)

    example = tok.apply_chat_template(build_messages("{입력 문장}"), add_generation_prompt=True, tokenize=False)
    with open(os.path.join(out_dir, "prompt.txt"), "w", encoding="utf-8") as f:
        f.write("[system prompt]\n" + SYSTEM_PROMPT + "\n\n[rendered chat template]\n" + example + "\n")

    gen_args = dict(max_new_tokens=MAX_NEW_TOKENS, do_sample=False, top_k=1, temperature=None, top_p=None,
                    repetition_penalty=1.0, pad_token_id=tok.pad_token_id or tok.eos_token_id)
    eos = model.generation_config.eos_token_id
    eos_ids = set(eos if isinstance(eos, list) else [eos]) | {tok.eos_token_id}

    rows = []
    t0 = time.time()
    for i, r in enumerate(dev):
        enc = tok.apply_chat_template(build_messages(r["입력 문장"]), add_generation_prompt=True,
                                      return_tensors="pt", return_dict=True).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, **gen_args)
        new = out[0][enc["input_ids"].shape[1]:]
        text = tok.decode(new, skip_special_tokens=True)
        items, parse_ok, schema_ok = parse_output(text)
        rows.append({"row": i + 1, **r, "raw_output": text, "items": items, "parse_ok": parse_ok,
                     "schema_ok": schema_ok, "truncated": int(new[-1]) not in eos_ids,
                     **score(r["gold1"], r["gold2"], items)})
        if (i + 1) % 20 == 0 or i + 1 == len(dev):
            print(f"[{i+1}/{len(dev)}] exact={sum(x['exact'] for x in rows)} "
                  f"parse_fail={sum(not x['parse_ok'] for x in rows)} {time.time()-t0:.0f}s", flush=True)

    assert md5(dev_path) == md5_before, "input changed"
    summary = {"model": MODEL_ID, "fine_tuned": False, "dev_file": dev_path, "dev_md5": md5_before,
               "n": len(rows), "prompt_fields_used": ["입력 문장"], "sec_total": round(time.time() - t0, 1),
               **summarize(rows)}
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    write_rows(rows, os.path.join(out_dir, "rows.csv"))
    write_rows(rows, os.path.join(out_dir, "wrong.csv"), only_wrong=True)

    info = {"model_id": MODEL_ID, "revision": MODEL_REVISION, "dtype": "bfloat16", "fine_tuned": False,
            "gpu": torch.cuda.get_device_name(0), "gpu_mem_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
            "torch": torch.__version__, "transformers": transformers.__version__, "seed": SEED,
            "decoding": {"temperature": "0 (do_sample=False, greedy)", "top_k": 1, "repetition_penalty": 1.0,
                         "max_new_tokens": MAX_NEW_TOKENS, "constrained_decoding": False},
            "model_generation_config": model.generation_config.to_dict(), "few_shot": 0,
            "chat_template": "official (tokenizer.apply_chat_template)", "batch_size": 1}
    json.dump(info, open(os.path.join(out_dir, "model_info.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=str)
    print("saved", out_dir, flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        selftest()
    else:
        main(sys.argv[2], sys.argv[3])
