"""Baseline eval: skt/A.X-4.0-Light (no fine-tuning) on eval.jsonl.

- Feeds only system + user messages; assistant message is the gold label (scoring only).
- Greedy decoding (do_sample=False == temperature 0).
- Parses JSON from output and compares nutrient / direction.
"""
import json, re, sys, time, collections, platform
import torch, transformers
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_ID = "skt/A.X-4.0-Light"
EVAL_PATH = sys.argv[1] if len(sys.argv) > 1 else "eval.jsonl"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "baseline_result.json"
MAX_NEW_TOKENS = 64
NUTRIENTS = ["calories", "protein", "sodium", "carbs", "sugar", "fat"]


def parse_output(text):
    """Returns (obj, mode). mode: 'strict' (whole output is JSON), 'extracted' (JSON found inside text), None (fail)."""
    s = text.strip()
    s_nofence = re.sub(r"^```(?:json)?\s*|\s*```$", "", s).strip()
    for cand, mode in ((s, "strict"), (s_nofence, "strict")):
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj, mode
        except json.JSONDecodeError:
            pass
    for m in re.finditer(r"\{[^{}]*\}", s):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj, "extracted"
        except json.JSONDecodeError:
            continue
    return None, None


def norm(v):
    return str(v).strip().lower() if v is not None else None


NUTRIENT_KEY_ALIASES = ("nutrient", "component", "성분", "영양성분", "영양 성분")
DIRECTIONS = ("high", "low")


def interpret(obj):
    """Semantic reading of a parsed dict -> (nutrient, direction, rule).
    strict rule: keys exactly {'nutrient','direction'} (gold schema).
    Lenient rules: alias key for nutrient (e.g. 'component'), or a single
    nutrient-name key whose value is high/low (e.g. {"sodium": "low"}).
    Multiple nutrient keys = ambiguous -> no answer."""
    if not isinstance(obj, dict):
        return None, None, "no_json"
    low = {norm(k): v for k, v in obj.items()}
    if set(low) == {"nutrient", "direction"}:
        return norm(low["nutrient"]), norm(low["direction"]), "exact_schema"
    for a in NUTRIENT_KEY_ALIASES:
        if a in low and norm(low[a]) in NUTRIENTS:
            return norm(low[a]), norm(low.get("direction")), "alias_key"
    nkeys = [k for k in low if k in NUTRIENTS and norm(low[k]) in DIRECTIONS]
    if len(nkeys) == 1:
        return nkeys[0], norm(low[nkeys[0]]), "nutrient_as_key"
    if len(nkeys) > 1:
        return None, None, "ambiguous_multi"
    return None, norm(low.get("direction")), "unknown_schema"


def score(gold, gen):
    obj, mode = parse_output(gen)
    gn, gd = norm(gold["nutrient"]), norm(gold["direction"])
    # strict: gold schema keys only
    sn = norm(obj.get("nutrient")) if obj else None
    sd = norm(obj.get("direction")) if obj else None
    ln, ld, rule = interpret(obj)
    return {
        "parse_mode": mode,
        "fenced": gen.strip().startswith("```"),
        "schema_rule": rule,
        "strict": {"pred": {"nutrient": sn, "direction": sd}, "nutrient_correct": sn == gn,
                   "direction_correct": sd == gd, "both_correct": sn == gn and sd == gd},
        "semantic": {"pred": {"nutrient": ln, "direction": ld}, "nutrient_correct": ln == gn,
                     "direction_correct": ld == gd, "both_correct": ln == gn and ld == gd},
    }


def summarize(results):
    n = len(results)
    def acc(level, key):
        return round(sum(x[level][key] for x in results) / n, 4)
    out = {}
    for level in ("strict", "semantic"):
        per = collections.OrderedDict()
        for nut in NUTRIENTS:
            xs = [x for x in results if norm(x["gold"]["nutrient"]) == nut]
            if xs:
                per[nut] = {"total": len(xs),
                            "nutrient_correct": sum(x[level]["nutrient_correct"] for x in xs),
                            "both_correct": sum(x[level]["both_correct"] for x in xs)}
                per[nut]["nutrient_acc"] = round(per[nut]["nutrient_correct"] / len(xs), 4)
                per[nut]["both_acc"] = round(per[nut]["both_correct"] / len(xs), 4)
        conf = collections.defaultdict(collections.Counter)
        for x in results:
            conf[x["gold"]["nutrient"]][x[level]["pred"]["nutrient"] or "NO_ANSWER"] += 1
        out[level] = {"nutrient_accuracy": acc(level, "nutrient_correct"),
                      "direction_accuracy": acc(level, "direction_correct"),
                      "both_accuracy": acc(level, "both_correct"),
                      "per_nutrient": per,
                      "confusion_gold_to_pred_nutrient": {k: dict(v) for k, v in conf.items()}}
    out["parse"] = {
        "parse_fail_count": sum(x["parse_mode"] is None for x in results),
        "json_parsed_count": sum(x["parse_mode"] is not None for x in results),
        "code_fenced_count": sum(x["fenced"] for x in results),
        "exact_gold_schema_count": sum(x["schema_rule"] == "exact_schema" for x in results),
        "schema_rule_counts": dict(collections.Counter(x["schema_rule"] for x in results)),
    }
    return out


def write_result(results, meta):
    s = summarize(results)
    summary = {**meta, **{"scoring_note": (
        "strict = keys must be exactly {nutrient, direction} like the gold label. "
        "semantic = same answer but key-name differences forgiven ('component' alias, or {\"<nutrient>\": \"high|low\"}); "
        "multiple nutrient keys count as no answer. Code fences (```json) are stripped before parsing in both.")}, **s}
    wrong = [{"idx": x["idx"], "user": x["user"], "gold": x["gold"], "raw_output": x["raw_output"],
              "strict_pred": x["strict"]["pred"], "semantic_pred": x["semantic"]["pred"],
              "schema_rule": x["schema_rule"], "wrong_in": [l for l in ("strict", "semantic") if not x[l]["both_correct"]]}
             for x in results if not x["strict"]["both_correct"] or not x["semantic"]["both_correct"]]
    out = {"summary": summary,
           "wrong_semantic": [w for w in wrong if "semantic" in w["wrong_in"]],
           "wrong_strict": [w for w in wrong if "strict" in w["wrong_in"]],
           "all_results": results}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("strict", "semantic")}, ensure_ascii=False, indent=2))
    for l in ("strict", "semantic"):
        print(l, {k: summary[l][k] for k in ("nutrient_accuracy", "direction_accuracy", "both_accuracy")})


def rescore(prev_path):
    """Re-score saved raw outputs (deterministic greedy run) without regenerating."""
    prev = json.load(open(prev_path, encoding="utf-8"))
    results = []
    for r in prev["all_results"]:
        base = {k: r[k] for k in ("idx", "user", "gold", "raw_output", "latency_sec")}
        results.append({**base, **score(r["gold"], r["raw_output"])})
    meta = {k: prev["summary"][k] for k in ("model", "fine_tuned", "eval_file", "n", "decoding",
                                             "avg_latency_sec", "total_time_sec", "env", "run_at")}
    meta["rescored_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write_result(results, meta)


def main():
    if len(sys.argv) > 3 and sys.argv[3] == "--rescore":
        return rescore(sys.argv[4] if len(sys.argv) > 4 else OUT_PATH)
    rows = [json.loads(l) for l in open(EVAL_PATH, encoding="utf-8") if l.strip()]
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
    model.eval()

    results = []
    t0 = time.time()
    for i, r in enumerate(rows):
        msgs = r["messages"]
        prompt_msgs = [m for m in msgs if m["role"] in ("system", "user")]
        gold = json.loads(next(m["content"] for m in msgs if m["role"] == "assistant"))
        ids = tok.apply_chat_template(prompt_msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(model.device)
        ts = time.time()
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                                 temperature=None, top_p=None, top_k=None,
                                 pad_token_id=tok.pad_token_id or tok.eos_token_id)
        gen = tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True)
        latency = time.time() - ts
        user = next(m["content"] for m in prompt_msgs if m["role"] == "user")
        results.append({"idx": i, "user": user, "gold": gold, "raw_output": gen,
                        "latency_sec": round(latency, 3), **score(gold, gen)})
        ok = results[-1]["semantic"]["both_correct"]
        print(f"[{i+1:02d}/{len(rows)}] {'OK ' if ok else 'NG '} {user[:30]!r} -> {gen.strip()[:80]!r}", flush=True)

    meta = {
        "model": MODEL_ID, "fine_tuned": False, "eval_file": "eval.jsonl", "n": len(results),
        "decoding": {"do_sample": False, "temperature": 0, "max_new_tokens": MAX_NEW_TOKENS, "dtype": "bfloat16"},
        "avg_latency_sec": round(sum(x["latency_sec"] for x in results) / len(results), 3),
        "total_time_sec": round(time.time() - t0, 1),
        "env": {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
                "transformers": transformers.__version__, "python": platform.python_version()},
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_result(results, meta)


if __name__ == "__main__":
    main()
