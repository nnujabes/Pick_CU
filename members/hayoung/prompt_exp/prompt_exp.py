"""Step 4: compare prompt variants on situations held out from train. No training.

Selection data: 18 train situations held out from the few-shot pool, so dev stays out of the selection.
A variant chosen here can then be confirmed once on dev (pool = all of train).
Only the sentence text is sent as the query. Few-shot labels come from other train situations only.

usage:
  python prompt_exp.py selftest <train_csv> <dev_csv>
  python prompt_exp.py val <train_csv> <out_dir>
  python prompt_exp.py dev <train_csv> <dev_csv> <variant> <out_dir>
"""
import collections
import csv
import importlib.util
import json
import math
import os
import random
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "base", os.path.join(SCRIPT_DIR, "..", "dev_2nut_baseline", "dev_2nut_baseline.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

SEED = 42
K = 8
MAX_PER_SITUATION = 2
PER_FIRST_NUTRIENT = 3  # 3 held-out situations for each of the 6 values of 성분1 = 18
# Situations behind the 10 rule examples. The rules reveal their labels, so they cannot be validation data.
RULE_SITUATIONS = {"S001", "S019", "S002", "S2001", "S2007", "S2014", "S2046", "S2042", "S022", "S2056", "S2065"}

RULES = base.SYSTEM_PROMPT.split("규칙 예시:\n")[1]
P1_SYSTEM = f"""당신은 편의점 영양 추천 도우미입니다. 사용자 문장을 보고 필요한 영양소 2개와 방향(높음/낮음)을 JSON으로만 답하세요.

출력 형식: {{"nutrients": [{{"nutrient": "성분", "direction": "방향"}}, {{"nutrient": "성분", "direction": "방향"}}]}}
성분: calories(열량), protein(단백질), sodium(나트륨), carbs(탄수화물), sugar(당류), fat(지방)
방향: high(높음), low(낮음)
성분과 방향은 위 영어 코드만 쓰고, 항상 서로 다른 성분 2개를 답하세요.

규칙 예시:
{RULES}"""

VARIANTS = {
    "P0_base": {"system": base.SYSTEM_PROMPT, "shots": None},
    "P1_format": {"system": P1_SYSTEM, "shots": None},
    "P2_static": {"system": P1_SYSTEM, "shots": "static"},
    "P3_tfidf": {"system": P1_SYSTEM, "shots": "tfidf"},
    "P4_embed": {"system": P1_SYSTEM, "shots": "embed"},
}


def read_rows(path):
    return base.read_dev(path)


def split_validation(train):
    rng = random.Random(SEED)
    by_first = collections.defaultdict(set)
    for r in train:
        if r["상황ID"] not in RULE_SITUATIONS:
            by_first[r["성분1"]].add(r["상황ID"])
    held = set()
    for first in sorted(by_first):
        held |= set(rng.sample(sorted(by_first[first]), PER_FIRST_NUTRIENT))
    return [r for r in train if r["상황ID"] in held], [r for r in train if r["상황ID"] not in held]


def label_json(r):
    return json.dumps({"nutrients": [{"nutrient": r["gold1"][0], "direction": r["gold1"][1]},
                                     {"nutrient": r["gold2"][0], "direction": r["gold2"][1]}]}, ensure_ascii=False)


def static_shots(pool):
    """K sentences from different situations, adding uncovered (nutrient, direction) pairs first."""
    rng = random.Random(SEED)
    rows = pool[:]
    rng.shuffle(rows)
    covered, used, shots = set(), set(), []
    while len(shots) < K:
        fresh = [r for r in rows if r["상황ID"] not in used]
        best = max(fresh, key=lambda r: len({r["gold1"], r["gold2"]} - covered))
        shots.append(best)
        used.add(best["상황ID"])
        covered |= {best["gold1"], best["gold2"]}
    return shots


def char_ngrams(text):
    t = "".join(text.split())
    return collections.Counter(t[i:i + n] for n in (2, 3, 4) for i in range(len(t) - n + 1))


class TfidfIndex:
    def __init__(self, sentences):
        grams = [char_ngrams(s) for s in sentences]
        df = collections.Counter(g for c in grams for g in c)
        n = len(sentences)
        self.idf = {g: math.log((1 + n) / (1 + v)) + 1 for g, v in df.items()}
        self.vecs = [self._norm(c) for c in grams]

    def _norm(self, counts):
        v = {g: (1 + math.log(c)) * self.idf[g] for g, c in counts.items() if g in self.idf}
        size = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / size for g, x in v.items()}

    def scores(self, sentence):
        q = self._norm(char_ngrams(sentence))
        return [sum(w * vec.get(g, 0.0) for g, w in q.items()) for vec in self.vecs]


def top_k(scores, pool, exclude_situation=None):
    """Best K rows, at most MAX_PER_SITUATION per situation. Returned least to most similar."""
    order = sorted(range(len(pool)), key=lambda i: -scores[i])
    picked, per = [], collections.Counter()
    for i in order:
        sit = pool[i]["상황ID"]
        assert sit != exclude_situation
        if per[sit] < MAX_PER_SITUATION:
            picked.append(pool[i])
            per[sit] += 1
            if len(picked) == K:
                break
    return picked[::-1]


def build_messages(system, shots, sentence):
    msgs = [{"role": "system", "content": system}]
    for s in shots:
        msgs += [{"role": "user", "content": s["입력 문장"]}, {"role": "assistant", "content": label_json(s)}]
    return msgs + [{"role": "user", "content": sentence}]


def knn_label(shots):
    """Retrieval-only reference without A.X: the label of the most similar sentence."""
    return [shots[-1]["gold1"], shots[-1]["gold2"]]


def score_rows(rows):
    return {"overall": base.overall(rows), **{k: base.summarize(rows)[k] for k in ("counts", "by_situation")}}


def embed_all(model, tok, sentences):
    import numpy as np
    import torch
    out = []
    for s in sentences:
        enc = tok(s, return_tensors="pt").to("cuda")
        with torch.no_grad():
            h = model(**enc, output_hidden_states=True).hidden_states[-1][0].float().mean(0)
        out.append((h / h.norm()).cpu().numpy())
    return np.stack(out)


def load_model():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
    set_seed(SEED)
    torch.backends.cudnn.deterministic = True
    tok = AutoTokenizer.from_pretrained(base.MODEL_ID, revision=base.MODEL_REVISION)
    model = AutoModelForCausalLM.from_pretrained(
        base.MODEL_ID, revision=base.MODEL_REVISION, dtype=torch.bfloat16, device_map="cuda")
    model.eval()
    return tok, model


def generate(tok, model, msgs, gen_args, eos_ids):
    import torch
    enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to("cuda")
    with torch.no_grad():
        out = model.generate(**enc, **gen_args)
    new = out[0][enc["input_ids"].shape[1]:]
    return tok.decode(new, skip_special_tokens=True), int(new[-1]) not in eos_ids


def run_variant(name, rows, pool, tok, model, gen_args, eos_ids, tfidf, pool_emb, query_emb, out_dir, label):
    cfg = VARIANTS[name]
    static = static_shots(pool) if cfg["shots"] == "static" else []
    results, knn_rows = [], []
    t0 = time.time()
    for i, r in enumerate(rows):
        if cfg["shots"] == "tfidf":
            shots = top_k(tfidf.scores(r["입력 문장"]), pool, r["상황ID"])
        elif cfg["shots"] == "embed":
            shots = top_k((pool_emb @ query_emb[i]).tolist(), pool, r["상황ID"])
        else:
            shots = static
        if i == 0:
            with open(os.path.join(out_dir, f"{label}_{name}_prompt_example.txt"), "w", encoding="utf-8") as f:
                f.write(tok.apply_chat_template(build_messages(cfg["system"], shots, r["입력 문장"]),
                                                add_generation_prompt=True, tokenize=False))
        text, truncated = generate(tok, model, build_messages(cfg["system"], shots, r["입력 문장"]), gen_args, eos_ids)
        items, parse_ok, schema_ok = base.parse_output(text)
        results.append({"row": i + 1, **r, "raw_output": text, "items": items, "parse_ok": parse_ok,
                        "schema_ok": schema_ok, "truncated": truncated,
                        **base.score(r["gold1"], r["gold2"], items)})
        if cfg["shots"] in ("tfidf", "embed"):
            knn_rows.append({**r, "items": knn_label(shots), **base.score(r["gold1"], r["gold2"], knn_label(shots))})
        if (i + 1) % 100 == 0 or i + 1 == len(rows):
            print(f"{name} [{i+1}/{len(rows)}] exact={sum(x['exact'] for x in results)} "
                  f"{time.time()-t0:.0f}s", flush=True)
    base.write_rows(results, os.path.join(out_dir, f"{label}_{name}_rows.csv"))
    summary = {**score_rows(results), "sec": round(time.time() - t0, 1)}
    if knn_rows:
        summary["retrieval_only_no_AX"] = base.overall(knn_rows)
    return summary


def prepare(rows, pool, tok, model):
    gen_args = dict(max_new_tokens=base.MAX_NEW_TOKENS, do_sample=False, top_k=1, temperature=None, top_p=None,
                    repetition_penalty=1.0, pad_token_id=tok.pad_token_id or tok.eos_token_id)
    eos = model.generation_config.eos_token_id
    eos_ids = set(eos if isinstance(eos, list) else [eos]) | {tok.eos_token_id}
    tfidf = TfidfIndex([r["입력 문장"] for r in pool])
    pool_emb = embed_all(model, tok, [r["입력 문장"] for r in pool])
    query_emb = embed_all(model, tok, [r["입력 문장"] for r in rows])
    print(f"indexes ready: pool={len(pool)} queries={len(rows)}", flush=True)
    return gen_args, eos_ids, tfidf, pool_emb, query_emb


def run_val(train_path, out_dir):
    train = read_rows(train_path)
    val, pool = split_validation(train)
    assert not {r["상황ID"] for r in val} & {r["상황ID"] for r in pool}
    print("validation situations:", sorted({r["상황ID"] for r in val}), len(val), flush=True)
    tok, model = load_model()
    prepared = prepare(val, pool, tok, model)
    out = {"split": {"val_situations": sorted({r["상황ID"] for r in val}), "n_val": len(val), "n_pool": len(pool)},
           "k": K, "max_per_situation": MAX_PER_SITUATION, "variants": {}}
    for name in VARIANTS:
        out["variants"][name] = run_variant(name, val, pool, tok, model, *prepared, out_dir, "val")
        json.dump(out, open(os.path.join(out_dir, "val_summary.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    print("saved", flush=True)


def run_dev(train_path, dev_path, variant, out_dir):
    pool, dev = read_rows(train_path), read_rows(dev_path)
    assert not {r["상황ID"] for r in pool} & {r["상황ID"] for r in dev}
    assert not {r["입력 문장"] for r in pool} & {r["입력 문장"] for r in dev}
    md5_before = base.md5(dev_path)
    tok, model = load_model()
    prepared = prepare(dev, pool, tok, model)
    summary = run_variant(variant, dev, pool, tok, model, *prepared, out_dir, "dev")
    assert base.md5(dev_path) == md5_before
    json.dump({"variant": variant, "dev_md5": md5_before, "n_pool": len(pool), **summary},
              open(os.path.join(out_dir, f"dev_{variant}_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("saved", flush=True)


def selftest(train_path, dev_path):
    train, dev = read_rows(train_path), read_rows(dev_path)
    val, pool = split_validation(train)
    val_ids, pool_ids = {r["상황ID"] for r in val}, {r["상황ID"] for r in pool}
    assert len(val_ids) == 18 and len(val) == 540 and len(pool) == 2160
    assert not val_ids & pool_ids and not val_ids & RULE_SITUATIONS
    assert split_validation(train)[0] == val
    assert len(static_shots(pool)) == K and len({r["상황ID"] for r in static_shots(pool)}) == K

    index = TfidfIndex([r["입력 문장"] for r in pool])
    for r in val[:20]:
        shots = top_k(index.scores(r["입력 문장"]), pool, r["상황ID"])
        assert len(shots) == K
        assert max(collections.Counter(s["상황ID"] for s in shots).values()) <= MAX_PER_SITUATION
        msgs = build_messages(P1_SYSTEM, shots, r["입력 문장"])
        prompt = json.dumps(msgs, ensure_ascii=False)
        assert r["상황ID"] not in prompt and r["작성자"] not in prompt
        # The query's own label may only appear if a different situation happens to share it.
        assert r["입력 문장"] not in {s["입력 문장"] for s in shots}
    same = TfidfIndex(["오늘 단백질 많은 거 먹을래", "달달한 케이크 먹고 싶어"]).scores("단백질 많은 간식")
    assert same[0] > same[1]
    try:
        top_k(index.scores(pool[0]["입력 문장"]), pool, pool[0]["상황ID"])
    except AssertionError:
        pass
    else:
        raise SystemExit("a query's own situation must be rejected")
    assert not {r["입력 문장"] for r in train} & {r["입력 문장"] for r in dev}
    print("selftest ok")
    print("validation:", sorted(val_ids))
    print("labels:", collections.Counter(f"{r['성분1']}{r['방향1']}/{r['성분2']}{r['방향2']}"
                                         for r in val).most_common())
    print(P1_SYSTEM)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "selftest":
        selftest(sys.argv[2], sys.argv[3])
    elif mode == "val":
        run_val(sys.argv[2], sys.argv[3])
    else:
        run_dev(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
