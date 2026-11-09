"""Ollama에 올린 GGUF 모델로 dev 216문장을 평가하고, 4bit+LoRA 기준 결과(종호 dev_4060)와 문장별로 비교한다.

사용: python eval_gguf.py <모델 이름> <출력 폴더>
채점은 query_parser.parse_model_response로 하고, 두 쌍이 모두 맞으면 정답(순서 무관)으로 본다.
"""
import csv
import json
import os
import sys
import time
import urllib.request

REPO = os.path.expanduser("~/Daive-LLM/pickcu")
sys.path.insert(0, os.path.join(REPO, "members/hayoung/finetune_v1/code"))
import query_parser as qp  # noqa: E402

MODEL, OUT = sys.argv[1], sys.argv[2]
DEV = os.path.join(REPO, "members/hayoung/dev_pair_v3_baseline/dev_pair_v3.csv")
REF = os.path.join(REPO, "members/jongho/eval/results/dev_4060/rows.csv")
KO2EN = {"열량": "calories", "단백질": "protein", "나트륨": "sodium", "탄수화물": "carbs", "당류": "sugar", "지방": "fat"}
DIR = {"높음": "high", "낮음": "low"}


def generate(text):
    body = json.dumps({"model": MODEL, "prompt": text, "stream": False,
                       "options": {"temperature": 0, "num_predict": 128}}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", body, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))["response"]


def as_set(nutrients):
    return {(KO2EN[name], direction) for name, direction in nutrients.items()}


rows = list(csv.DictReader(open(DEV, encoding="utf-8-sig")))
ref = {r["입력 문장"]: r for r in csv.DictReader(open(REF, encoding="utf-8-sig"))}
os.makedirs(OUT, exist_ok=True)
results, start = [], time.time()
generate("워밍업")
start = time.time()
for i, r in enumerate(rows, 1):
    gold = {(KO2EN[r["성분1"]], DIR[r["방향1"]]), (KO2EN[r["성분2"]], DIR[r["방향2"]])}
    raw = generate(r["입력 문장"])
    parsed, reason = qp.parse_model_response(raw)
    pred = as_set(parsed) if parsed else None
    ref_row = ref.get(r["입력 문장"])
    ref_pred = None
    if ref_row and ref_row["예측"]:
        ref_pred = {tuple(p.strip().split("/")) for p in ref_row["예측"].split(",")}
    results.append({
        "row": i, "입력 문장": r["입력 문장"], "정답": sorted(gold), "예측": sorted(pred) if pred else None,
        "맞음": pred == gold, "형식오류": reason, "기준_예측": sorted(ref_pred) if ref_pred else None,
        "기준과_같음": pred == ref_pred, "raw": raw,
    })
    if i % 50 == 0:
        print(f"{i}/{len(rows)} ({time.time() - start:.0f}s)", flush=True)

elapsed = time.time() - start
correct = sum(x["맞음"] for x in results)
same = sum(x["기준과_같음"] for x in results)
bad = sum(x["형식오류"] is not None for x in results)
ref_correct = sum(1 for x in results if x["기준_예측"] and set(map(tuple, x["기준_예측"])) == set(map(tuple, x["정답"])))
summary = {"model": MODEL, "n": len(results), "correct": correct, "acc": round(correct / len(results), 4),
           "reference_correct": ref_correct, "same_as_reference": same, "format_errors": bad,
           "seconds": round(elapsed, 1), "sec_per_sentence": round(elapsed / len(results), 2)}
json.dump(summary, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(results, open(os.path.join(OUT, "rows.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False))
