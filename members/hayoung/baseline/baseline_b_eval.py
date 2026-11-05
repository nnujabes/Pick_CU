"""Baseline B: skt/A.X-4.0-Light (no fine-tuning) + explicit output format + few-shot from train.jsonl.

Same as baseline A except:
  - system prompt states the exact JSON schema (no code fences / no explanation)
  - one few-shot example per (nutrient, direction) label found in train.jsonl (9 labels -> 9 shots),
    picked with a fixed seed, never using eval sentences (exact or near-duplicate, difflib ratio >= 0.8)
Eval set, greedy decoding, bf16, scoring (strict + semantic) are identical to A (functions reused).
"""
import json, sys, time, random, difflib, re, collections, platform
import torch, transformers
from transformers import AutoTokenizer, AutoModelForCausalLM
import baseline_eval as A  # reuse parse/score/summarize/write logic

A.OUT_PATH = sys.argv[3] if len(sys.argv) > 3 else "baseline_b_result.json"
TRAIN_PATH = sys.argv[1] if len(sys.argv) > 1 else "train.jsonl"
EVAL_PATH = sys.argv[2] if len(sys.argv) > 2 else "eval.jsonl"
SEED = 42
NEAR_DUP_RATIO = 0.8

SYSTEM_B = (
    "사용자의 편의점 식품 요청을 읽고, 가장 중요한 영양 성분 1개와 그 방향을 판단하세요.\n"
    '반드시 {"nutrient": "...", "direction": "..."} 형식의 JSON 한 줄로만 답하세요.\n'
    "- nutrient: calories, protein, sodium, carbs, sugar, fat 중 정확히 1개\n"
    "- direction: high, low 중 정확히 1개\n"
    "설명, 코드블록(```), 다른 키는 절대 쓰지 마세요. JSON만 출력하세요."
)


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def parts(r):
    m = r["messages"]
    return (next(x["content"] for x in m if x["role"] == "user"),
            json.loads(next(x["content"] for x in m if x["role"] == "assistant")))


def pick_fewshot(train, eval_users):
    norm = lambda s: re.sub(r"\s+", "", s)
    ev = [norm(u) for u in eval_users]
    groups = collections.OrderedDict()
    for r in train:
        u, g = parts(r)
        groups.setdefault((g["nutrient"], g["direction"]), []).append((u, g))
    order = [(n, d) for n in A.NUTRIENTS for d in ("high", "low") if (n, d) in groups]
    rng = random.Random(SEED)
    shots, rejected = [], []
    for key in order:
        cands = groups[key][:]
        rng.shuffle(cands)
        for u, g in cands:
            nu = norm(u)
            sim = max(difflib.SequenceMatcher(None, nu, e).ratio() for e in ev)
            if nu in ev or sim >= NEAR_DUP_RATIO:
                rejected.append({"user": u, "max_sim_to_eval": round(sim, 3)})
                continue
            shots.append({"user": u, "gold": {"nutrient": g["nutrient"], "direction": g["direction"]},
                          "max_sim_to_eval": round(sim, 3)})
            break
    return shots, rejected


def main():
    train, rows = load(TRAIN_PATH), load(EVAL_PATH)
    eval_users = [parts(r)[0] for r in rows]
    shots, rejected = pick_fewshot(train, eval_users)
    assert not {s["user"] for s in shots} & set(eval_users)
    fewshot_msgs = []
    for s in shots:
        fewshot_msgs += [{"role": "user", "content": s["user"]},
                         {"role": "assistant", "content": json.dumps(s["gold"], ensure_ascii=False)}]
    print("few-shot:", json.dumps(shots, ensure_ascii=False, indent=1), flush=True)

    tok = AutoTokenizer.from_pretrained(A.MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(A.MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
    model.eval()

    results, t0 = [], time.time()
    for i, r in enumerate(rows):
        user, gold = parts(r)
        msgs = [{"role": "system", "content": SYSTEM_B}] + fewshot_msgs + [{"role": "user", "content": user}]
        ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(model.device)
        ts = time.time()
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=A.MAX_NEW_TOKENS, do_sample=False,
                                 temperature=None, top_p=None, top_k=None,
                                 pad_token_id=tok.pad_token_id or tok.eos_token_id)
        gen = tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True)
        results.append({"idx": i, "user": user, "gold": gold, "raw_output": gen,
                        "latency_sec": round(time.time() - ts, 3), **A.score(gold, gen)})
        ok = results[-1]["strict"]["both_correct"]
        print(f"[{i+1:02d}/{len(rows)}] {'OK ' if ok else 'NG '} {user[:30]!r} -> {gen.strip()[:80]!r}", flush=True)

    meta = {
        "baseline": "B", "model": A.MODEL_ID, "fine_tuned": False, "eval_file": "eval.jsonl", "n": len(results),
        "decoding": {"do_sample": False, "temperature": 0, "max_new_tokens": A.MAX_NEW_TOKENS, "dtype": "bfloat16"},
        "changes_vs_A": ["system prompt states exact JSON schema", f"{len(shots)} few-shot examples from train.jsonl"],
        "system_prompt": SYSTEM_B,
        "fewshot": {"seed": SEED, "rule": "1 random example per (nutrient,direction) label in train.jsonl; "
                    f"skip if exact or near-duplicate (difflib ratio >= {NEAR_DUP_RATIO}) of any eval sentence",
                    "examples": shots, "rejected_as_too_close_to_eval": rejected,
                    "overlap_with_eval": 0},
        "prompt_tokens_example": int(ids["input_ids"].shape[1]),
        "avg_latency_sec": round(sum(x["latency_sec"] for x in results) / len(results), 3),
        "total_time_sec": round(time.time() - t0, 1),
        "env": {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
                "transformers": transformers.__version__, "python": platform.python_version()},
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    A.write_result(results, meta)


if __name__ == "__main__":
    main()
