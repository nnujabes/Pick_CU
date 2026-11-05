"""Dev baseline: skt/A.X-4.0-Light (no fine-tuning) on dev.csv (216 rows).

Prompt = system (task + 6 nutrients + 2 directions + JSON format) + 9 few-shot examples from train.csv
+ ONLY the '입력 문장' text of each dev row. Gold labels (성분/방향) are used only for scoring after generation.
Greedy decoding (do_sample=False == temperature 0), bf16.

usage: python dev_baseline.py train.csv dev.csv out_prefix
"""
import csv, json, re, sys, time, random, difflib, collections

MODEL_ID = "skt/A.X-4.0-Light"
MAX_NEW_TOKENS = 64
SEED = 42

NUT_MAP = {"열량": "calories", "단백질": "protein", "나트륨": "sodium", "탄수화물": "carbs", "당류": "sugar", "지방": "fat"}
DIR_MAP = {"높음": "high", "낮음": "low"}
NUTRIENTS = ["calories", "protein", "sodium", "carbs", "sugar", "fat"]
DIRECTIONS = ["high", "low"]

SYSTEM_PROMPT = """당신은 편의점 식품 추천을 돕는 분류기입니다.
사용자의 문장을 읽고, 그 요청에서 가장 중요한 영양 성분 1개와 그 방향(높음/낮음)을 판단하세요.

영양 성분 (nutrient) — 아래 6개 중 정확히 1개:
- calories (열량)
- protein (단백질)
- sodium (나트륨)
- carbs (탄수화물)
- sugar (당류)
- fat (지방)

방향 (direction) — 아래 2개 중 정확히 1개:
- high (높음: 많이 들어있는 것을 원함)
- low (낮음: 적게 들어있는 것을 원함)

출력 형식: {"nutrient": "sodium", "direction": "high"} 와 같은 JSON 한 줄만 출력하세요.
설명, 코드블록(```), 다른 키는 절대 쓰지 마세요."""

# 9 few-shot labels: all 6 nutrients appear, 5 high / 4 low.
# train.csv has no (sodium, high) and no (protein, low) rows, so those can't be used.
FEWSHOT_LABELS = [
    ("calories", "high"), ("calories", "low"),
    ("protein", "high"),
    ("sodium", "low"),
    ("carbs", "high"), ("carbs", "low"),
    ("sugar", "high"),
    ("fat", "high"), ("fat", "low"),
]


def read_csv(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    out = []
    for r in rows:
        if not (r["입력 문장"] or "").strip():
            continue  # skip fully-empty rows
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        r["nutrient"] = NUT_MAP[r["성분"]]
        r["direction"] = DIR_MAP[r["방향"]]
        out.append(r)
    return out


def pick_fewshot(train, dev_sents):
    rng = random.Random(SEED)
    used_styles = collections.Counter()
    shots = []
    for nut, d in FEWSHOT_LABELS:
        cands = [r for r in train if r["nutrient"] == nut and r["direction"] == d]
        rng.shuffle(cands)
        # prefer a 말투 유형 not used yet, and never anything close to a dev sentence
        cands.sort(key=lambda r: used_styles[r["말투 유형"]])
        for r in cands:
            if max(difflib.SequenceMatcher(None, r["입력 문장"], s).ratio() for s in dev_sents) < 0.8:
                shots.append(r)
                used_styles[r["말투 유형"]] += 1
                break
    assert len(shots) == 9
    return shots


def label_json(nut, d):
    return json.dumps({"nutrient": nut, "direction": d}, ensure_ascii=False)


def build_messages(shots, sentence):
    """sentence is the ONLY dev field that goes into the prompt."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for s in shots:
        msgs.append({"role": "user", "content": s["입력 문장"]})
        msgs.append({"role": "assistant", "content": label_json(s["nutrient"], s["direction"])})
    msgs.append({"role": "user", "content": sentence})
    return msgs


def parse_output(text):
    """Returns (obj or None, parse_ok)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t).strip()
    try:
        return json.loads(t), True
    except Exception:
        pass
    m = re.search(r"\{[^{}]*\}", t)
    if m:
        try:
            return json.loads(m.group(0)), True
        except Exception:
            pass
    return None, False


def extract_pred(obj):
    if not isinstance(obj, dict):
        return None, None
    n = obj.get("nutrient"); d = obj.get("direction")
    n = n.strip().lower() if isinstance(n, str) else None
    d = d.strip().lower() if isinstance(d, str) else None
    return (n if n in NUTRIENTS else None), (d if d in DIRECTIONS else None)


def acc(rows, key):
    return {"correct": sum(r[key] for r in rows), "n": len(rows),
            "acc": round(sum(r[key] for r in rows) / len(rows), 4) if rows else None}


def group_acc(rows, field):
    g = collections.defaultdict(list)
    for r in rows:
        g[r[field]].append(r)
    return {k: {"both": acc(v, "both_ok"), "nutrient": acc(v, "nut_ok"), "direction": acc(v, "dir_ok")}
            for k, v in sorted(g.items())}


def main(train_path, dev_path, out_prefix):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    train = read_csv(train_path)
    dev = read_csv(dev_path)
    print(f"train={len(train)} dev={len(dev)}", flush=True)
    shots = pick_fewshot(train, [r["입력 문장"] for r in dev])
    dev_set = set(r["입력 문장"] for r in dev)
    assert not any(s["입력 문장"] in dev_set for s in shots)
    print("few-shot:", flush=True)
    for s in shots:
        print(f"  [{s['nutrient']}/{s['direction']}] ({s['말투 유형']}) {s['입력 문장']}", flush=True)

    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
    model.eval()
    print(f"model loaded, GPU mem {torch.cuda.memory_allocated()/2**30:.1f} GiB", flush=True)

    results = []
    t0 = time.time()
    for i, r in enumerate(dev):
        msgs = build_messages(shots, r["입력 문장"])
        enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                                 pad_token_id=tok.pad_token_id or tok.eos_token_id)
        text = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        obj, ok = parse_output(text)
        pn, pd = extract_pred(obj) if ok else (None, None)
        res = {
            "row": i + 1, "상황ID": r["상황ID"], "작성자": r["작성자"], "말투 유형": r["말투 유형"],
            "입력 문장": r["입력 문장"], "gold_nutrient": r["nutrient"], "gold_direction": r["direction"],
            "pred_nutrient": pn or "", "pred_direction": pd or "", "raw_output": text,
            "parse_ok": ok, "schema_ok": bool(pn and pd),
        }
        res["nut_ok"] = pn == r["nutrient"]
        res["dir_ok"] = pd == r["direction"]
        res["both_ok"] = res["nut_ok"] and res["dir_ok"]
        results.append(res)
        if (i + 1) % 20 == 0 or i + 1 == len(dev):
            n = i + 1
            print(f"[{n}/{len(dev)}] both={sum(x['both_ok'] for x in results)}/{n} "
                  f"parse_fail={sum(not x['parse_ok'] for x in results)} {time.time()-t0:.0f}s", flush=True)

    # confusion: gold nutrient x predicted nutrient (+ invalid)
    cols = NUTRIENTS + ["(invalid)"]
    conf = {g: {c: 0 for c in cols} for g in NUTRIENTS}
    for x in results:
        conf[x["gold_nutrient"]][x["pred_nutrient"] or "(invalid)"] += 1

    summary = {
        "model": MODEL_ID, "fine_tuned": False, "dev_file": dev_path, "n": len(results),
        "decoding": {"do_sample": False, "temperature": 0, "max_new_tokens": MAX_NEW_TOKENS, "dtype": "bfloat16"},
        "prompt_fields_used": ["입력 문장"],
        "fewshot": [{"sentence": s["입력 문장"], "nutrient": s["nutrient"], "direction": s["direction"],
                     "상황ID": s["상황ID"], "말투 유형": s["말투 유형"]} for s in shots],
        "system_prompt": SYSTEM_PROMPT,
        "overall": {"both": acc(results, "both_ok"), "nutrient": acc(results, "nut_ok"),
                    "direction": acc(results, "dir_ok")},
        "parse_fail": sum(not x["parse_ok"] for x in results),
        "schema_invalid_but_parsed": sum(x["parse_ok"] and not x["schema_ok"] for x in results),
        "by_gold_nutrient": group_acc(results, "gold_nutrient"),
        "by_gold_direction": group_acc(results, "gold_direction"),
        "by_situation": group_acc(results, "상황ID"),
        "by_author": group_acc(results, "작성자"),
        "by_style": group_acc(results, "말투 유형"),
        "confusion_nutrient": conf,
        "wrong": [{k: x[k] for k in ("row", "상황ID", "입력 문장", "gold_nutrient", "gold_direction",
                                     "pred_nutrient", "pred_direction", "raw_output")}
                  for x in results if not x["both_ok"]],
        "sec_total": round(time.time() - t0, 1),
    }
    json.dump(summary, open(out_prefix + "_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    fields = ["row", "상황ID", "작성자", "말투 유형", "입력 문장", "정답", "예측", "결과",
              "gold_nutrient", "gold_direction", "pred_nutrient", "pred_direction",
              "nut_ok", "dir_ok", "both_ok", "parse_ok", "raw_output"]
    with open(out_prefix + "_rows.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for x in results:
            row = {k: x.get(k, "") for k in fields}
            row["정답"] = label_json(x["gold_nutrient"], x["gold_direction"])
            row["예측"] = label_json(x["pred_nutrient"], x["pred_direction"]) if x["schema_ok"] else x["raw_output"]
            row["결과"] = "맞음" if x["both_ok"] else "틀림"
            w.writerow(row)
    print("saved", out_prefix + "_summary.json", out_prefix + "_rows.csv", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
