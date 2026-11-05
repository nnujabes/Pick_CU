"""QLoRA 1단계: train_pair_v3.csv → SFT jsonl (상황 단위 train/val 분할), 마스킹 확인, 토큰 길이 분포.
dev는 읽지 않는다. test는 열지 않는다. 입력 CSV는 읽기만 한다.

usage: python prepare_data.py <train_csv> <baseline_prompt_txt> <baseline_script_py> <out_dir>
"""
import collections
import csv
import hashlib
import importlib.util
import json
import os
import random
import statistics
import sys

SEED = 42
N_VAL = 9  # 94상황의 약 10%
EXPECTED_SYS_SHA = "06818f0f2ba2c5ac7f05454846c37e9054766184d62cd521b6afe0eab479b556"
RULE_SITS = {"S001", "S019", "S2014", "S2046", "S2042", "S2001", "S2056", "S2065", "S2024", "S2030"}
NUT = {"열량": "calories", "단백질": "protein", "나트륨": "sodium", "탄수화물": "carbs", "당류": "sugar", "지방": "fat"}
DIR = {"높음": "high", "낮음": "low"}
MODEL_ID = "skt/A.X-4.0-Light"
MODEL_REVISION = "ba21c20ea1b31ded1ec3e2fb432335077dc4be98"


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_system_prompt(prompt_txt, script_py):
    prev = open(prompt_txt, encoding="utf-8").read()
    from_txt = prev.split("[system prompt]\n", 1)[1].split("\n\n[rendered chat template]\n", 1)[0]
    spec = importlib.util.spec_from_file_location("b", script_py)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    h_txt, h_py = sha(from_txt), sha(m.SYSTEM_PROMPT)
    print(f"system prompt sha256: prompt.txt={h_txt} script={h_py} expected={EXPECTED_SYS_SHA}")
    if not (h_txt == h_py == EXPECTED_SYS_SHA):
        sys.exit("STOP: system prompt hash mismatch")
    return from_txt, h_txt


def answer_json(r):
    obj = {"nutrients": [{"nutrient": NUT[r["성분1"]], "direction": DIR[r["방향1"]]},
                         {"nutrient": NUT[r["성분2"]], "direction": DIR[r["방향2"]]}]}
    return json.dumps(obj, ensure_ascii=False)  # 베이스라인 프롬프트 예시와 같은 형식(", " / ": ")


def split_situations(rows):
    first = {}
    for r in rows:
        first.setdefault(r["상황ID"], (r["성분1"], r["방향1"]))
    eligible = sorted(s for s in first if s not in RULE_SITS)
    by_label = collections.defaultdict(list)
    for s in eligible:
        by_label[first[s]].append(s)
    rng = random.Random(SEED)
    labels = sorted(by_label)
    rng.shuffle(labels)
    for lab in labels:
        rng.shuffle(by_label[lab])
    # 라벨을 돌아가며 한 상황씩 뽑는다 → 라벨당 최대 1개(9 < 라벨 종류 수일 때)
    val, i = [], 0
    while len(val) < N_VAL:
        lab = labels[i % len(labels)]
        if by_label[lab]:
            val.append(by_label[lab].pop())
        i += 1
    return set(val), first


def main(train_csv, prompt_txt, script_py, out):
    os.makedirs(out, exist_ok=True)
    md5_before = hashlib.md5(open(train_csv, "rb").read()).hexdigest()
    system, sys_sha = load_system_prompt(prompt_txt, script_py)
    rows = [r for r in csv.DictReader(open(train_csv, encoding="utf-8-sig")) if r["상황ID"].strip()]
    assert len(rows) == 2820, len(rows)
    val_sits, first = split_situations(rows)

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)

    recs = {"train": [], "val": []}
    lens, ans_lens = [], []
    for r in rows:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": r["입력 문장"]},
                {"role": "assistant", "content": answer_json(r)}]
        prompt_ids = tok.apply_chat_template(msgs[:2], add_generation_prompt=True, tokenize=True, return_dict=True)["input_ids"]
        full_ids = tok.apply_chat_template(msgs, tokenize=True, return_dict=True)["input_ids"]
        assert full_ids[:len(prompt_ids)] == prompt_ids, "prompt prefix mismatch"
        lens.append(len(full_ids))
        ans_lens.append(len(full_ids) - len(prompt_ids))
        part = "val" if r["상황ID"] in val_sits else "train"
        recs[part].append({"상황ID": r["상황ID"], "말투 유형": r["말투 유형"], "messages": msgs,
                           "n_prompt_tokens": len(prompt_ids), "n_tokens": len(full_ids)})

    for part in recs:
        with open(os.path.join(out, f"{part}_sft.jsonl"), "w", encoding="utf-8") as f:
            for x in recs[part]:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(os.path.join(out, "split_info.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["상황ID", "성분1", "방향1", "구분", "문장 수"])
        cnt = collections.Counter(r["상황ID"] for r in rows)
        for s in sorted(first):
            w.writerow([s, first[s][0], first[s][1], "val" if s in val_sits else "train", cnt[s]])

    # 마스킹 확인: 샘플 1개
    x = recs["train"][0]
    full = tok.apply_chat_template(x["messages"], tokenize=True, return_dict=True)["input_ids"]
    labels = [-100] * x["n_prompt_tokens"] + full[x["n_prompt_tokens"]:]
    masked = tok.decode(full[:x["n_prompt_tokens"]])
    learned = tok.decode([t for t, l in zip(full, labels) if l != -100])
    eos_id = tok.convert_tokens_to_ids("<|im_end|>")

    def pct(a, p):
        a = sorted(a)
        return a[min(len(a) - 1, int(round(p / 100 * (len(a) - 1))))]

    def dist(part, key):
        return dict(collections.Counter(key(x) for x in recs[part]).most_common())

    info = {
        "train_csv": train_csv, "train_csv_md5": md5_before, "system_prompt_sha256": sys_sha,
        "seed": SEED, "rule_situations_excluded_from_val": sorted(RULE_SITS),
        "val_situations": sorted(val_sits),
        "counts": {p: {"situations": len({x["상황ID"] for x in recs[p]}), "sentences": len(recs[p])} for p in recs},
        "label_dist_sentences": {p: dist(p, lambda x: "".join(first[x["상황ID"]])) for p in recs},
        "label_dist_situations": {p: dict(collections.Counter("".join(first[s]) for s in {x["상황ID"] for x in recs[p]}).most_common()) for p in recs},
        "style_dist": {p: dist(p, lambda x: x["말투 유형"]) for p in recs},
        "token_len": {"mean": round(statistics.mean(lens), 1), "max": max(lens), "min": min(lens),
                      "p95": pct(lens, 95), "p99": pct(lens, 99)},
        "answer_token_len": {"mean": round(statistics.mean(ans_lens), 1), "max": max(ans_lens), "min": min(ans_lens)},
        "masking_sample": {"상황ID": x["상황ID"], "n_tokens": len(full), "n_masked": x["n_prompt_tokens"],
                           "n_learned": len(full) - x["n_prompt_tokens"],
                           "masked_tail": masked[-80:], "learned_text": learned,
                           "learned_ends_with_im_end": full[-1] == eos_id or learned.rstrip().endswith("<|im_end|>")},
        "md5_unchanged": hashlib.md5(open(train_csv, "rb").read()).hexdigest() == md5_before,
    }
    json.dump(info, open(os.path.join(out, "data_info.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(info, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
