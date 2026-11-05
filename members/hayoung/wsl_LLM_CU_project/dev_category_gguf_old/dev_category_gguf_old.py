"""Dev-category baseline: skt/A.X-4.0-Light Q4_K_M GGUF (no fine-tuning) via llama-cpp-python on local RTX 4060.

Task: from ONE sentence predict
  category  = list of 1-3 recommended CU categories (multi-label, order ignored)
  nutrient  = calories/protein/sodium/carbs/sugar/fat
  direction = high/low
Only the '입력 문장' text of each dev row goes into the prompt. Gold columns are used for scoring only.
Prompt is rendered with the OFFICIAL chat template (skt tokenizer_config.json; verified identical to the GGUF's)
and passed as token ids. Greedy (temperature 0), no grammar / constrained decoding.

usage: python dev_category_gguf.py train_category.csv dev_category.csv out_dir
"""
import csv, json, os, re, sys, time, random, difflib, collections, hashlib, platform

GGUF_PATH = "/home/ai/models/ax-gguf/A.X-4.0-Light-Q4_K_M.gguf"
GGUF_REPO = "mykor/A.X-4.0-Light-gguf"
GGUF_FILE = "A.X-4.0-Light-Q4_K_M.gguf"
TOKENIZER_DIR = "/home/ai/models/ax-official-tokenizer"  # skt/A.X-4.0-Light tokenizer files
N_CTX = 4096
MAX_TOKENS = 96
SEED = 42

NUT_MAP = {"열량": "calories", "단백질": "protein", "나트륨": "sodium", "탄수화물": "carbs", "당류": "sugar", "지방": "fat"}
DIR_MAP = {"높음": "high", "낮음": "low"}
NUTRIENTS = ["calories", "protein", "sodium", "carbs", "sugar", "fat"]
DIRECTIONS = ["high", "low"]
CATEGORIES = ["간편식사", "과자류", "식품", "음료", "아이스크림"]  # all values found in train/dev
CAT_COLS = ["카테고리1", "카테고리2", "카테고리3"]

SYSTEM_PROMPT = """당신은 편의점 식품 추천을 돕는 분류기입니다.
사용자의 문장을 읽고 아래 3가지를 판단하세요.

1. category — 이 요청에 맞는 편의점 상품 카테고리를 아래 5개 중에서 1~3개 골라 리스트로 답하세요.
- 간편식사
- 과자류
- 식품
- 음료
- 아이스크림

2. nutrient — 요청에서 가장 중요한 영양 성분을 아래 6개 중 정확히 1개:
- calories (열량)
- protein (단백질)
- sodium (나트륨)
- carbs (탄수화물)
- sugar (당류)
- fat (지방)

3. direction — 그 성분의 방향을 아래 2개 중 정확히 1개:
- high (높음: 많이 들어있는 것을 원함)
- low (낮음: 적게 들어있는 것을 원함)

출력 형식: {"category": ["간편식사", "음료"], "nutrient": "sodium", "direction": "low"} 와 같은 JSON 한 줄만 출력하세요.
설명, 코드블록(```), 다른 키는 절대 쓰지 마세요."""

# 9 few-shot labels. train has NO (sodium, high) and NO (protein, low) rows, so those are excluded.
# (label, number of categories) -> mixes 1/2/3-category examples
FEWSHOT_PLAN = [
    (("calories", "high"), 3), (("calories", "low"), 1),
    (("protein", "high"), 2),
    (("sodium", "low"), 3),
    (("carbs", "high"), 1), (("carbs", "low"), 2),
    (("sugar", "high"), 3),
    (("fat", "high"), 2), (("fat", "low"), 1),
]


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def read_csv(path):
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        if not (r["입력 문장"] or "").strip():
            continue  # skip the fully-empty row
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        r["nutrient"] = NUT_MAP[r["성분"]]
        r["direction"] = DIR_MAP[r["방향"]]
        cats = [r[c] for c in CAT_COLS if r.get(c)]
        assert all(c in CATEGORIES for c in cats), cats
        r["cats"] = sorted(set(cats), key=CATEGORIES.index)
        out.append(r)
    return out


def pick_fewshot(train, dev_sents):
    rng = random.Random(SEED)
    used_styles = collections.Counter()
    shots = []
    for (nut, d), ncat in FEWSHOT_PLAN:
        cands = [r for r in train if r["nutrient"] == nut and r["direction"] == d and len(r["cats"]) == ncat]
        rng.shuffle(cands)
        cands.sort(key=lambda r: used_styles[r["말투 유형"]])  # vary 말투 유형
        for r in cands:
            if max(difflib.SequenceMatcher(None, r["입력 문장"], s).ratio() for s in dev_sents) < 0.8:
                shots.append(r)
                used_styles[r["말투 유형"]] += 1
                break
    assert len(shots) == 9, len(shots)
    return shots


def label_json(cats, nut, d):
    return json.dumps({"category": cats, "nutrient": nut, "direction": d}, ensure_ascii=False)


def build_messages(shots, sentence):
    """`sentence` is the ONLY dev field that goes into the prompt."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for s in shots:
        msgs.append({"role": "user", "content": s["입력 문장"]})
        msgs.append({"role": "assistant", "content": label_json(s["cats"], s["nutrient"], s["direction"])})
    msgs.append({"role": "user", "content": sentence})
    return msgs


def parse_output(text):
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip()).strip()
    try:
        return json.loads(t), True
    except Exception:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a != -1 and b > a:
        try:
            return json.loads(t[a:b + 1]), True
        except Exception:
            pass
    return None, False


def extract_pred(obj):
    """-> (cats list or None, invalid cat names, nutrient or None, direction or None)"""
    if not isinstance(obj, dict):
        return None, [], None, None
    c = obj.get("category")
    if isinstance(c, str):
        c = [c]
    cats, bad = None, []
    if isinstance(c, list):
        names = [x.strip() for x in c if isinstance(x, str)]
        bad = [x for x in names if x not in CATEGORIES]
        cats = sorted(set(x for x in names if x in CATEGORIES), key=CATEGORIES.index)
    n = obj.get("nutrient"); d = obj.get("direction")
    n = n.strip().lower() if isinstance(n, str) else None
    d = d.strip().lower() if isinstance(d, str) else None
    return cats, bad, (n if n in NUTRIENTS else None), (d if d in DIRECTIONS else None)


def acc(rows, key):
    c = sum(r[key] for r in rows)
    return {"correct": c, "n": len(rows), "acc": round(c / len(rows), 4) if rows else None}


def group_acc(rows, keyfn):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyfn(r)].append(r)
    return {k: {m: acc(v, f) for m, f in (("all3", "all_ok"), ("category", "cat_ok"), ("nutrient", "nut_ok"),
                                         ("direction", "dir_ok"), ("nut_dir", "nd_ok"))}
            for k, v in sorted(g.items())}


def main(train_path, dev_path, out_dir):
    import llama_cpp
    from transformers import AutoTokenizer
    os.makedirs(out_dir, exist_ok=True)

    train = read_csv(train_path)
    dev = read_csv(dev_path)
    print(f"train={len(train)} dev={len(dev)}", flush=True)
    shots = pick_fewshot(train, [r["입력 문장"] for r in dev])
    assert not set(s["입력 문장"] for s in shots) & set(r["입력 문장"] for r in dev)
    print("few-shot:", flush=True)
    for s in shots:
        print(f"  {label_json(s['cats'], s['nutrient'], s['direction'])} ({s['말투 유형']}) {s['입력 문장']}", flush=True)

    tok = AutoTokenizer.from_pretrained(TOKENIZER_DIR)
    llm = llama_cpp.Llama(GGUF_PATH, n_gpu_layers=-1, n_ctx=N_CTX, seed=SEED, verbose=False)
    md = llm.metadata
    official_tmpl = json.load(open(os.path.join(TOKENIZER_DIR, "tokenizer_config.json")))["chat_template"]
    assert md.get("tokenizer.chat_template") == official_tmpl, "GGUF chat template differs from official"
    print(f"model loaded: {GGUF_FILE} n_ctx={N_CTX} n_gpu_layers=-1 (all {md.get('qwen2.block_count')} layers)", flush=True)

    # save the exact prompt for the first dev row (as a sample) + few-shot
    sample_prompt = tok.apply_chat_template(build_messages(shots, "<입력 문장>"), tokenize=False, add_generation_prompt=True)
    open(os.path.join(out_dir, "prompt.txt"), "w", encoding="utf-8").write(
        "=== SYSTEM PROMPT ===\n" + SYSTEM_PROMPT + "\n\n=== RENDERED PROMPT (official chat template) ===\n" + sample_prompt + "\n")
    json.dump([{"입력 문장": s["입력 문장"], "category": s["cats"], "nutrient": s["nutrient"], "direction": s["direction"],
                "상황ID": s["상황ID"], "말투 유형": s["말투 유형"]} for s in shots],
              open(os.path.join(out_dir, "fewshot.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    results, times, max_prompt = [], [], 0
    t0 = time.time()
    for i, r in enumerate(dev):
        ids = tok.apply_chat_template(build_messages(shots, r["입력 문장"]), tokenize=True,
                                      add_generation_prompt=True, return_dict=True)["input_ids"]
        ids = list(ids)
        max_prompt = max(max_prompt, len(ids))
        assert len(ids) + MAX_TOKENS <= N_CTX
        ts = time.time()
        out = llm.create_completion(ids, max_tokens=MAX_TOKENS, temperature=0.0, top_k=1, top_p=1.0,
                                    repeat_penalty=1.0, seed=SEED)
        times.append(time.time() - ts)
        llm.reset()
        text = out["choices"][0]["text"]
        obj, ok = parse_output(text)
        pc, bad, pn, pd = extract_pred(obj) if ok else (None, [], None, None)
        x = {"row": i + 1, "상황ID": r["상황ID"], "작성자": r["작성자"], "말투 유형": r["말투 유형"], "입력 문장": r["입력 문장"],
             "gold_cats": r["cats"], "gold_nutrient": r["nutrient"], "gold_direction": r["direction"],
             "pred_cats": pc, "pred_bad_cats": bad, "pred_nutrient": pn, "pred_direction": pd,
             "raw_output": text, "parse_ok": ok, "finish": out["choices"][0].get("finish_reason")}
        x["cat_ok"] = pc is not None and not bad and set(pc) == set(r["cats"])
        x["nut_ok"] = pn == r["nutrient"]
        x["dir_ok"] = pd == r["direction"]
        x["nd_ok"] = x["nut_ok"] and x["dir_ok"]
        x["all_ok"] = x["cat_ok"] and x["nd_ok"]
        results.append(x)
        if (i + 1) % 20 == 0 or i + 1 == len(dev):
            n = i + 1
            print(f"[{n}/{len(dev)}] all3={sum(y['all_ok'] for y in results)}/{n} nut+dir={sum(y['nd_ok'] for y in results)}/{n} "
                  f"cat={sum(y['cat_ok'] for y in results)}/{n} parse_fail={sum(not y['parse_ok'] for y in results)} "
                  f"{time.time()-t0:.0f}s ({sum(times)/len(times):.2f}s/문장)", flush=True)

    # ---- category multi-label stats
    per_cat = {}
    for c in CATEGORIES:
        tp = sum(1 for x in results if c in x["gold_cats"] and x["pred_cats"] and c in x["pred_cats"])
        fp = sum(1 for x in results if c not in x["gold_cats"] and x["pred_cats"] and c in x["pred_cats"])
        fn = sum(1 for x in results if c in x["gold_cats"] and not (x["pred_cats"] and c in x["pred_cats"]))
        per_cat[c] = {"gold": tp + fn, "pred": tp + fp, "TP": tp, "FP(지어냄)": fp, "FN(누락)": fn,
                      "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                      "recall": round(tp / (tp + fn), 4) if tp + fn else None}
    TP = sum(v["TP"] for v in per_cat.values()); FP = sum(v["FP(지어냄)"] for v in per_cat.values())
    FN = sum(v["FN(누락)"] for v in per_cat.values())
    jac = [len(set(x["gold_cats"]) & set(x["pred_cats"] or [])) / len(set(x["gold_cats"]) | set(x["pred_cats"] or []))
           for x in results]
    combo = collections.Counter((" + ".join(x["gold_cats"]), " + ".join(x["pred_cats"] or ["(없음/실패)"])) for x in results)

    conf = {g: {c: 0 for c in NUTRIENTS + ["(invalid)"]} for g in NUTRIENTS}
    for x in results:
        conf[x["gold_nutrient"]][x["pred_nutrient"] or "(invalid)"] += 1

    model_info = {
        "gguf_repo": GGUF_REPO, "gguf_file": GGUF_FILE, "gguf_path": GGUF_PATH,
        "gguf_sha256": "6bd9cb8ccaae2efc5c33c7b5e443c2f820d4731130df38cd24f7ba494146ead5",
        "base_model": "skt/A.X-4.0-Light", "quantization": "Q4_K_M (general.file_type=15)",
        "chat_template": "official skt/A.X-4.0-Light tokenizer_config.json (verified identical to GGUF-embedded)",
        "n_ctx": N_CTX, "n_gpu_layers": -1, "max_tokens": MAX_TOKENS, "max_prompt_tokens": max_prompt,
        "decoding": {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "repeat_penalty": 1.0, "seed": SEED, "grammar": None},
        "runtime": {"llama_cpp_python": llama_cpp.__version__, "gpu": "NVIDIA GeForce RTX 4060 Laptop GPU 8GB",
                    "python": platform.python_version(), "conda_env": "axgguf"},
        "speed": {"sec_per_sentence_avg": round(sum(times) / len(times), 3), "sec_total": round(time.time() - t0, 1)},
        "inputs": {"dev": dev_path, "dev_md5": md5(dev_path), "train": train_path, "train_md5": md5(train_path)},
    }
    json.dump(model_info, open(os.path.join(out_dir, "model_info.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    summary = {
        "model_info": model_info, "n": len(results), "prompt_fields_used": ["입력 문장"],
        "excluded_fewshot_labels": ["sodium/high (train에 없음)", "protein/low (train에 없음)"],
        "overall": {m: acc(results, f) for m, f in (("all3", "all_ok"), ("category", "cat_ok"), ("nutrient", "nut_ok"),
                                                    ("direction", "dir_ok"), ("nut_dir", "nd_ok"))},
        "parse_fail": sum(not x["parse_ok"] for x in results),
        "category_missing_in_parsed": sum(x["parse_ok"] and x["pred_cats"] is None for x in results),
        "invalid_category_names": collections.Counter(b for x in results for b in x["pred_bad_cats"]),
        "category_multilabel": {"micro_precision": round(TP / (TP + FP), 4) if TP + FP else None,
                                "micro_recall": round(TP / (TP + FN), 4) if TP + FN else None,
                                "mean_jaccard": round(sum(jac) / len(jac), 4),
                                "FP_total(지어냄)": FP, "FN_total(누락)": FN,
                                "gold_count_dist": collections.Counter(len(x["gold_cats"]) for x in results),
                                "pred_count_dist": collections.Counter(len(x["pred_cats"] or []) for x in results),
                                "per_category": per_cat},
        "category_combo_confusion": [{"gold": g, "pred": p, "n": n} for (g, p), n in combo.most_common()],
        "by_gold_category_set": group_acc(results, lambda x: " + ".join(x["gold_cats"])),
        "by_gold_nutrient": group_acc(results, lambda x: x["gold_nutrient"]),
        "by_gold_direction": group_acc(results, lambda x: x["gold_direction"]),
        "by_situation": group_acc(results, lambda x: x["상황ID"]),
        "by_author": group_acc(results, lambda x: x["작성자"]),
        "confusion_nutrient": conf,
        "wrong": [{k: x[k] for k in ("row", "상황ID", "입력 문장", "gold_cats", "gold_nutrient", "gold_direction",
                                     "pred_cats", "pred_nutrient", "pred_direction", "cat_ok", "nut_ok", "dir_ok", "raw_output")}
                  for x in results if not x["all_ok"]],
    }
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    fields = ["row", "상황ID", "작성자", "말투 유형", "입력 문장",
              "정답_카테고리", "정답_성분", "정답_방향", "예측_카테고리", "예측_성분", "예측_방향",
              "카테고리_맞음", "성분_맞음", "방향_맞음", "성분방향_맞음", "전체_맞음", "결과", "파싱_성공", "모델_원문출력"]
    with open(os.path.join(out_dir, "rows.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for x in results:
            w.writerow({"row": x["row"], "상황ID": x["상황ID"], "작성자": x["작성자"], "말투 유형": x["말투 유형"],
                        "입력 문장": x["입력 문장"], "정답_카테고리": "|".join(x["gold_cats"]),
                        "정답_성분": x["gold_nutrient"], "정답_방향": x["gold_direction"],
                        "예측_카테고리": "|".join(x["pred_cats"] or []), "예측_성분": x["pred_nutrient"] or "",
                        "예측_방향": x["pred_direction"] or "", "카테고리_맞음": x["cat_ok"], "성분_맞음": x["nut_ok"],
                        "방향_맞음": x["dir_ok"], "성분방향_맞음": x["nd_ok"], "전체_맞음": x["all_ok"],
                        "결과": "맞음" if x["all_ok"] else "틀림", "파싱_성공": x["parse_ok"], "모델_원문출력": x["raw_output"]})
    print("saved to", out_dir, flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
