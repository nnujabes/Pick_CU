"""Dev-category baseline v2: skt/A.X-4.0-Light Q4_K_M GGUF (no fine-tuning), llama-cpp-python on local RTX 4060.

Task (one sentence ->)
  categories = 1-3 suitable CU categories, most relevant first (gold = UNORDERED set of 카테고리1~3, never null)
  nutrient   = calories/protein/sodium/carbs/sugar/fat
  direction  = high/low
Only the '입력 문장' text of each dev row goes into the prompt; gold columns are used for scoring only.
Prompt is rendered with the OFFICIAL chat template (skt tokenizer_config.json, verified identical to the GGUF's)
and fed as token ids. Greedy (temperature 0), no grammar / constrained decoding.

usage: python dev_category_gguf.py train_category.csv dev_category.csv out_dir
"""
import csv, json, os, sys, time, random, difflib, collections, hashlib, platform

GGUF_PATH = "/home/ai/models/ax-gguf/A.X-4.0-Light-Q4_K_M.gguf"
GGUF_REPO = "mykor/A.X-4.0-Light-gguf"
GGUF_FILE = "A.X-4.0-Light-Q4_K_M.gguf"
GGUF_SHA256 = "6bd9cb8ccaae2efc5c33c7b5e443c2f820d4731130df38cd24f7ba494146ead5"
TOKENIZER_DIR = "/home/ai/models/ax-official-tokenizer"  # skt/A.X-4.0-Light tokenizer files
N_CTX = 4096
MAX_TOKENS = 96
SEED = 42

NUT_MAP = {"열량": "calories", "단백질": "protein", "나트륨": "sodium", "탄수화물": "carbs", "당류": "sugar", "지방": "fat"}
DIR_MAP = {"높음": "high", "낮음": "low"}
NUTRIENTS = ["calories", "protein", "sodium", "carbs", "sugar", "fat"]
DIRECTIONS = ["high", "low"]
CATEGORIES = ["간편식사", "식품", "과자류", "음료", "아이스크림"]
CAT_COLS = ["카테고리1", "카테고리2", "카테고리3"]

SYSTEM_PROMPT = """당신은 편의점 식품 추천을 돕는 분류기입니다.
사용자의 문장을 읽고 아래 3가지를 판단하세요.

1. categories — 이 요청에 어울리는 편의점 상품 카테고리를 아래 5개 중에서만 1~3개 골라, 관련도가 높은 순서대로 리스트로 답하세요. 최소 1개는 반드시 답하세요.
- 간편식사
- 식품
- 과자류
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

출력 형식: {"categories": ["간편식사", "식품"], "nutrient": "sodium", "direction": "low"} 와 같은 JSON 한 줄만 출력하세요.
설명, 코드블록(```), 다른 키는 절대 쓰지 마세요."""

# 12 few-shot slots: (nutrient, direction), number of gold categories.
# 6 nutrients, 6 high / 6 low, 4 each of 1/2/3-category examples.
# train has NO (sodium, high) and NO (protein, low) rows -> excluded.
FEWSHOT_PLAN = [
    (("calories", "high"), 3), (("calories", "low"), 1),
    (("protein", "high"), 2), (("protein", "high"), 3),
    (("sodium", "low"), 3), (("sodium", "low"), 2),
    (("carbs", "high"), 1), (("carbs", "low"), 2),
    (("sugar", "high"), 3), (("sugar", "low"), 1),
    (("fat", "high"), 2), (("fat", "low"), 1),
]


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def read_csv(path):
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        if not (r["입력 문장"] or "").strip():
            continue  # the one fully-empty row in train
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        r["nutrient"] = NUT_MAP[r["성분"]]
        r["direction"] = DIR_MAP[r["방향"]]
        r["cats"] = [r[c] for c in CAT_COLS if r[c]]  # order exactly as written in the data
        assert r["cats"] and all(c in CATEGORIES for c in r["cats"]) and len(set(r["cats"])) == len(r["cats"])
        out.append(r)
    return out


def pick_fewshot(train, dev):
    dev_sents = [r["입력 문장"] for r in dev]
    dev_sits = set(r["상황ID"] for r in dev)
    rng = random.Random(SEED)
    used_styles, used_sits, shots = collections.Counter(), set(), []
    for (nut, d), ncat in FEWSHOT_PLAN:
        cands = [r for r in train if r["nutrient"] == nut and r["direction"] == d and len(r["cats"]) == ncat
                 and r["상황ID"] not in dev_sits and r["입력 문장"] not in dev_sents]
        rng.shuffle(cands)
        # prefer unused situations and unused 말투 유형
        cands.sort(key=lambda r: (r["상황ID"] in used_sits, used_styles[r["말투 유형"]]))
        for r in cands:
            if max(difflib.SequenceMatcher(None, r["입력 문장"], s).ratio() for s in dev_sents) < 0.8:
                shots.append(r)
                used_styles[r["말투 유형"]] += 1
                used_sits.add(r["상황ID"])
                break
        else:
            raise RuntimeError(f"no few-shot candidate for {(nut, d)} with {ncat} categories")
    return shots


def label_json(cats, nut, d):
    return json.dumps({"categories": cats, "nutrient": nut, "direction": d}, ensure_ascii=False)


def build_messages(shots, sentence):
    """`sentence` is the ONLY dev field that goes into the prompt."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for s in shots:
        msgs.append({"role": "user", "content": s["입력 문장"]})
        msgs.append({"role": "assistant", "content": label_json(s["cats"], s["nutrient"], s["direction"])})
    msgs.append({"role": "user", "content": sentence})
    return msgs


def parse_output(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:] if t.lower().startswith("json") else t
        t = t.strip()
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
    """-> dict with ordered valid categories, invalid names, nutrient, direction, notes"""
    p = {"cats": [], "bad": [], "nutrient": None, "direction": None, "notes": []}
    if not isinstance(obj, dict):
        p["notes"].append("not_object")
        return p
    c = obj.get("categories")
    if c is None:
        p["notes"].append("no_categories_key")
    if isinstance(c, str):
        c = [c]
    if isinstance(c, list):
        for x in c:
            x = x.strip() if isinstance(x, str) else str(x)
            if x not in CATEGORIES:
                p["bad"].append(x)
            elif x not in p["cats"]:
                p["cats"].append(x)
            else:
                p["notes"].append("dup_category")
    if len(p["cats"]) > 3:
        p["notes"].append("more_than_3")
    n = obj.get("nutrient"); d = obj.get("direction")
    n = n.strip().lower() if isinstance(n, str) else None
    d = d.strip().lower() if isinstance(d, str) else None
    p["nutrient"] = n if n in NUTRIENTS else None
    p["direction"] = d if d in DIRECTIONS else None
    return p


def frac(rows, key):
    c = sum(1 for r in rows if r[key])
    return {"correct": c, "n": len(rows), "acc": round(c / len(rows), 4) if rows else None}


def mean(rows, key):
    return round(sum(r[key] for r in rows) / len(rows), 4) if rows else None


def metrics(rows):
    return {"nut_dir": frac(rows, "nd_ok"), "nutrient": frac(rows, "nut_ok"), "direction": frac(rows, "dir_ok"),
            "cat_exact": frac(rows, "cat_exact"), "cat_recall_mean": mean(rows, "cat_recall"),
            "cat_precision_mean": mean(rows, "cat_precision"), "cat_top1": frac(rows, "cat_top1"),
            "overall_a_exact": frac(rows, "all_a"), "overall_b_recall100": frac(rows, "all_b")}


def group(rows, keyfn):
    g = collections.defaultdict(list)
    for r in rows:
        for k in keyfn(r):
            g[k].append(r)
    return {k: metrics(v) for k, v in sorted(g.items())}


def main(train_path, dev_path, out_dir):
    import llama_cpp
    from transformers import AutoTokenizer
    os.makedirs(out_dir, exist_ok=True)

    train = read_csv(train_path)
    dev = read_csv(dev_path)
    print(f"train={len(train)} dev={len(dev)}", flush=True)
    shots = pick_fewshot(train, dev)
    print(f"few-shot ({len(shots)}):", flush=True)
    for s in shots:
        print(f"  [{s['상황ID']}|{s['말투 유형']}] {s['입력 문장']}  ->  {label_json(s['cats'], s['nutrient'], s['direction'])}", flush=True)

    tok = AutoTokenizer.from_pretrained(TOKENIZER_DIR)
    llm = llama_cpp.Llama(GGUF_PATH, n_gpu_layers=-1, n_ctx=N_CTX, seed=SEED, verbose=False)
    md = llm.metadata
    official_tmpl = json.load(open(os.path.join(TOKENIZER_DIR, "tokenizer_config.json")))["chat_template"]
    assert md.get("tokenizer.chat_template") == official_tmpl, "GGUF chat template differs from official"
    print(f"model loaded: {GGUF_FILE} ({md.get('general.file_type')}=Q4_K_M) n_ctx={N_CTX} "
          f"n_gpu_layers=-1 (all {md.get('qwen2.block_count')} layers on GPU)", flush=True)

    sample = tok.apply_chat_template(build_messages(shots, "<입력 문장>"), tokenize=False, add_generation_prompt=True)
    open(os.path.join(out_dir, "prompt.txt"), "w", encoding="utf-8").write(
        "=== SYSTEM PROMPT ===\n" + SYSTEM_PROMPT +
        "\n\n=== RENDERED PROMPT (official chat template; <입력 문장> is replaced by each dev sentence) ===\n" + sample + "\n")
    json.dump([{"상황ID": s["상황ID"], "말투 유형": s["말투 유형"], "입력 문장": s["입력 문장"], "categories": s["cats"],
                "nutrient": s["nutrient"], "direction": s["direction"]} for s in shots],
              open(os.path.join(out_dir, "fewshot.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    results, times, max_prompt = [], [], 0
    t0 = time.time()
    for i, r in enumerate(dev):
        ids = list(tok.apply_chat_template(build_messages(shots, r["입력 문장"]), tokenize=True,
                                           add_generation_prompt=True, return_dict=True)["input_ids"])
        max_prompt = max(max_prompt, len(ids))
        assert len(ids) + MAX_TOKENS <= N_CTX
        ts = time.time()
        out = llm.create_completion(ids, max_tokens=MAX_TOKENS, temperature=0.0, top_k=1, top_p=1.0,
                                    min_p=0.0, repeat_penalty=1.0, seed=SEED)
        times.append(time.time() - ts)
        llm.reset()
        text = out["choices"][0]["text"]
        obj, ok = parse_output(text)
        p = extract_pred(obj) if ok else {"cats": [], "bad": [], "nutrient": None, "direction": None, "notes": ["parse_fail"]}
        gold = set(r["cats"]); pred = set(p["cats"])
        x = {"row": i + 1, "상황ID": r["상황ID"], "작성자": r["작성자"], "말투 유형": r["말투 유형"], "입력 문장": r["입력 문장"],
             "gold_cats": r["cats"], "gold_nutrient": r["nutrient"], "gold_direction": r["direction"],
             "pred_cats": p["cats"], "pred_bad_cats": p["bad"], "pred_nutrient": p["nutrient"],
             "pred_direction": p["direction"], "notes": p["notes"], "raw_output": text, "parse_ok": ok,
             "finish": out["choices"][0].get("finish_reason")}
        x["nut_ok"] = p["nutrient"] == r["nutrient"]
        x["dir_ok"] = p["direction"] == r["direction"]
        x["nd_ok"] = x["nut_ok"] and x["dir_ok"]
        x["cat_exact"] = bool(pred) and pred == gold and not p["bad"]
        x["cat_recall"] = len(gold & pred) / len(gold)
        x["cat_precision"] = (len(gold & pred) / (len(pred) + len(p["bad"]))) if (pred or p["bad"]) else 0.0
        x["cat_top1"] = bool(p["cats"]) and p["cats"][0] in gold
        x["cat_missed"] = [c for c in r["cats"] if c not in pred]
        x["cat_added"] = [c for c in p["cats"] if c not in gold] + p["bad"]
        x["all_a"] = x["nd_ok"] and x["cat_exact"]
        x["all_b"] = x["nd_ok"] and x["cat_recall"] == 1.0
        results.append(x)
        if (i + 1) % 20 == 0 or i + 1 == len(dev):
            n = i + 1
            print(f"[{n}/{len(dev)}] 성분+방향={sum(y['nd_ok'] for y in results)}/{n} "
                  f"카테고리 완전일치={sum(y['cat_exact'] for y in results)}/{n} "
                  f"포함률={sum(y['cat_recall'] for y in results)/n:.3f} "
                  f"(a)={sum(y['all_a'] for y in results)}/{n} (b)={sum(y['all_b'] for y in results)}/{n} "
                  f"parse_fail={sum(not y['parse_ok'] for y in results)} | {time.time()-t0:.0f}s, "
                  f"{sum(times)/len(times):.2f}s/문장", flush=True)

    # ---- category confusion analysis
    per_cat = {}
    for c in CATEGORIES:
        g_rows = [x for x in results if c in x["gold_cats"]]
        per_cat[c] = {
            "gold_count": len(g_rows),
            "predicted_when_gold(포함)": sum(1 for x in g_rows if c in x["pred_cats"]),
            "missed(빠뜨림)": sum(1 for x in g_rows if c not in x["pred_cats"]),
            "added_when_not_gold(잘못 추가)": sum(1 for x in results if c not in x["gold_cats"] and c in x["pred_cats"]),
            "pred_count": sum(1 for x in results if c in x["pred_cats"]),
            "pred_as_top1": sum(1 for x in results if x["pred_cats"][:1] == [c]),
        }
        pc = per_cat[c]
        pc["recall"] = round(pc["predicted_when_gold(포함)"] / pc["gold_count"], 4) if pc["gold_count"] else None
        pc["precision"] = round(pc["predicted_when_gold(포함)"] / pc["pred_count"], 4) if pc["pred_count"] else None
    combo = collections.Counter((" + ".join(sorted(x["gold_cats"], key=CATEGORIES.index)),
                                 " + ".join(sorted(x["pred_cats"], key=CATEGORIES.index)) or "(없음)") for x in results)
    conf = {g: {c: 0 for c in NUTRIENTS + ["(invalid)"]} for g in NUTRIENTS}
    for x in results:
        conf[x["gold_nutrient"]][x["pred_nutrient"] or "(invalid)"] += 1

    tp = sum(len(set(x["gold_cats"]) & set(x["pred_cats"])) for x in results)
    npred = sum(len(x["pred_cats"]) + len(x["pred_bad_cats"]) for x in results)
    ngold = sum(len(x["gold_cats"]) for x in results)

    model_info = {
        "gguf_repo": GGUF_REPO, "gguf_file": GGUF_FILE, "gguf_path": GGUF_PATH, "gguf_sha256": GGUF_SHA256,
        "base_model": "skt/A.X-4.0-Light", "quantization": "Q4_K_M (general.file_type=15)",
        "chat_template": "official skt/A.X-4.0-Light tokenizer_config.json chat_template (verified identical to the GGUF-embedded one); prompt passed as token ids",
        "n_ctx": N_CTX, "n_gpu_layers": -1, "layers_on_gpu": f"{md.get('qwen2.block_count')}/{md.get('qwen2.block_count')}",
        "max_new_tokens": MAX_TOKENS, "max_prompt_tokens": max_prompt,
        "decoding": {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0, "repeat_penalty": 1.0, "seed": SEED,
                     "grammar": None},
        "runtime": {"llama_cpp_python": llama_cpp.__version__, "gpu": "NVIDIA GeForce RTX 4060 Laptop GPU (8GB)",
                    "python": platform.python_version(), "conda_env": "axgguf (WSL2 Ubuntu)"},
        "speed": {"sec_per_sentence_avg": round(sum(times) / len(times), 3), "sec_total": round(time.time() - t0, 1)},
        "inputs": {"dev": dev_path, "dev_md5": md5(dev_path), "train": train_path, "train_md5": md5(train_path)},
    }
    json.dump(model_info, open(os.path.join(out_dir, "model_info.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    summary = {
        "model_info": model_info, "n": len(results), "prompt_fields_used": ["입력 문장"],
        "fewshot_excluded_labels": ["sodium/high (train에 없음)", "protein/low (train에 없음)"],
        "overall": metrics(results),
        "parse_fail": sum(not x["parse_ok"] for x in results),
        "format_notes": collections.Counter(n for x in results for n in x["notes"]),
        "invalid_category_names": collections.Counter(b for x in results for b in x["pred_bad_cats"]),
        "category": {
            "exact": frac(results, "cat_exact"), "recall_mean": mean(results, "cat_recall"),
            "precision_mean": mean(results, "cat_precision"), "top1": frac(results, "cat_top1"),
            "micro_recall": round(tp / ngold, 4), "micro_precision": round(tp / npred, 4) if npred else None,
            "recall_100_rows": sum(1 for x in results if x["cat_recall"] == 1.0),
            "pred_count_mean": round(sum(len(x["pred_cats"]) for x in results) / len(results), 3),
            "pred_count_dist": dict(sorted(collections.Counter(len(x["pred_cats"]) for x in results).items())),
            "gold_count_mean": round(ngold / len(results), 3),
            "gold_count_dist": dict(sorted(collections.Counter(len(x["gold_cats"]) for x in results).items())),
            "per_category": per_cat,
            "combo_gold_vs_pred": [{"gold": g, "pred": p, "n": n} for (g, p), n in combo.most_common()],
        },
        "by_gold_category": group(results, lambda x: x["gold_cats"]),
        "by_gold_nutrient": group(results, lambda x: [x["gold_nutrient"]]),
        "by_gold_direction": group(results, lambda x: [x["gold_direction"]]),
        "by_situation": group(results, lambda x: [x["상황ID"]]),
        "by_author": group(results, lambda x: [x["작성자"]]),
        "confusion_nutrient": conf,
    }
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    fields = ["row", "상황ID", "작성자", "말투 유형", "입력 문장",
              "정답_성분", "정답_방향", "정답_카테고리", "예측_성분", "예측_방향", "예측_카테고리(순서대로)",
              "성분_맞음", "방향_맞음", "성분방향_맞음", "카테고리_완전일치", "카테고리_포함률", "카테고리_정밀도",
              "카테고리_1순위일치", "빠뜨린_카테고리", "잘못추가한_카테고리", "전체(a)_완전일치", "전체(b)_포함100",
              "파싱_성공", "모델_원문출력"]

    def to_row(x):
        return {"row": x["row"], "상황ID": x["상황ID"], "작성자": x["작성자"], "말투 유형": x["말투 유형"],
                "입력 문장": x["입력 문장"], "정답_성분": x["gold_nutrient"], "정답_방향": x["gold_direction"],
                "정답_카테고리": "|".join(x["gold_cats"]), "예측_성분": x["pred_nutrient"] or "",
                "예측_방향": x["pred_direction"] or "", "예측_카테고리(순서대로)": "|".join(x["pred_cats"] + x["pred_bad_cats"]),
                "성분_맞음": x["nut_ok"], "방향_맞음": x["dir_ok"], "성분방향_맞음": x["nd_ok"],
                "카테고리_완전일치": x["cat_exact"], "카테고리_포함률": round(x["cat_recall"], 4),
                "카테고리_정밀도": round(x["cat_precision"], 4), "카테고리_1순위일치": x["cat_top1"],
                "빠뜨린_카테고리": "|".join(x["cat_missed"]), "잘못추가한_카테고리": "|".join(x["cat_added"]),
                "전체(a)_완전일치": x["all_a"], "전체(b)_포함100": x["all_b"], "파싱_성공": x["parse_ok"],
                "모델_원문출력": x["raw_output"]}

    for fname, sel in (("rows.csv", results), ("wrong_nutrient_direction.csv", [x for x in results if not x["nd_ok"]]),
                       ("wrong_category.csv", [x for x in results if not x["cat_exact"]])):
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for x in sel:
                w.writerow(to_row(x))
    print("saved to", os.path.abspath(out_dir), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
