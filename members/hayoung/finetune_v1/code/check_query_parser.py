"""query_parser.py 확인 테스트. test 데이터는 쓰지 않고, 정답 열도 읽지 않는다. 입력 CSV는 읽기만 한다.

usage (ft_ax_v1/code 에서):
    python check_query_parser.py offline   # GPU 불필요: 예산, 응답 변환, 재시도 흐름
    python check_query_parser.py gpu       # 전체 흐름. 다른 사용자가 GPU를 쓰면 빌 때까지 대기
"""
import csv
import hashlib
import json
import logging
import os
import random
import statistics
import subprocess
import sys
import time

import query_parser as qp

HERE = os.path.dirname(os.path.abspath(__file__))
FT = os.path.dirname(HERE)
ROOT = os.path.dirname(FT)
OUT = os.path.join(FT, "results", "query_parser_check_v2")  # v1 = 재시도·길이 제한 수정 전 결과
TRAIN_CSV = os.path.join(ROOT, "data", "train_pair_v3.csv")
DEV_CSV = os.path.join(ROOT, "data", "dev_pair_v3.csv")
PREV_DEV_ROWS = os.path.join(FT, "results", "run_r16_lr2e-4", "dev_best", "rows.csv")
SEED = 42

BUDGET_CASES = [
    # 지원 표현
    ("6500원 정도로", 6500), ("6,500원 이내", 6500), ("5천원 이하", 5000), ("5천 원 이하", 5000),
    ("1만5천원으로", 15000), ("1만 5천 원으로", 15000), ("7천5백원 안쪽", 7500), ("만 원 정도", 10000),
    ("만원 쯤", 10000), ("천원 있어", 1000), ("오천원으로", 5000), ("삼천원 이내", 3000),
    ("2만원대로", 20000), ("5천원대", 5000), ("12,000원", 12000), ("3000 원", 3000),
    ("만오천원", 15000), ("이만원", 20000), ("삼천오백원", 3500), ("천오백원", 1500),
    ("오백원", 500), ("1만5000원", 15000), ("2.5만원", 25000), ("예산5천원", 5000),
    ("한 만원 정도", 10000), ("이만 오천 원", 25000), ("십만원", 100000), ("1,234,000원", 1234000),
    # 금액이 여럿: 먼저 나온 금액
    ("3천원에서 5천원 사이", 3000), ("만원 말고 오천원", 10000), ("2개에 5천원", 5000), ("30% 할인해서 3천원", 3000),
    # 조사 '만'과 붙은 금액
    ("단백질만 5천원으로", 5000), ("이것만 오천원에", 5000),
    # 금액이 아님
    ("2개 사고 싶어", None), ("3일 동안 먹을 거", None), ("5분 안에", None), ("30% 할인", None),
    ("500ml 음료", None), ("5천 정도", None), ("오천으로", None), ("1만5천", None),
    ("단백질 많은 걸 원해요", None), ("이것만 원해", None), ("그냥 만 원해요", None), ("3 원해", None),
    ("회사원인데 점심 추천", None), ("대학원 발표 전에", None), ("병원 가는 길에", None), ("강원도 여행", None),
    ("원래 안 좋아해", None), ("사원증 찍고", None), ("구원투수처럼", None), ("가족의 일원", None),
    ("몇천원 정도", None), ("몇 천원", None), ("수만원", None), ("0원", None), ("", None), ("   ", None),
]

RESPONSE_CASES = [
    ("정상", '{"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "fat", "direction": "low"}]}', {"단백질": "high", "지방": "low"}),
    ("앞뒤 잡글", '답은 다음과 같습니다. {"nutrients":[{"nutrient":"sodium","direction":"low"},{"nutrient":"sugar","direction":"high"}]} 이상입니다 {', {"나트륨": "low", "당류": "high"}),
    ("코드 펜스", '```json\n{"nutrients":[{"nutrient":"carbs","direction":"low"},{"nutrient":"calories","direction":"low"}]}\n```', {"탄수화물": "low", "열량": "low"}),
    ("다른 객체 뒤", '{"note": 1} {"nutrients":[{"nutrient":"carbs","direction":"low"},{"nutrient":"fat","direction":"low"}]}', {"탄수화물": "low", "지방": "low"}),
    ("1개", '{"nutrients":[{"nutrient":"carbs","direction":"low"}]}', None),
    ("3개", '{"nutrients":[{"nutrient":"carbs","direction":"low"},{"nutrient":"fat","direction":"low"},{"nutrient":"sugar","direction":"low"}]}', None),
    ("중복", '{"nutrients":[{"nutrient":"fat","direction":"low"},{"nutrient":"fat","direction":"high"}]}', None),
    ("밖의 성분", '{"nutrients":[{"nutrient":"fiber","direction":"high"},{"nutrient":"fat","direction":"low"}]}', None),
    ("틀린 방향", '{"nutrients":[{"nutrient":"protein","direction":"medium"},{"nutrient":"fat","direction":"low"}]}', None),
    ("비문자 성분", '{"nutrients":[{"nutrient":["protein"],"direction":"high"},{"nutrient":"fat","direction":"low"}]}', None),
    ("끊긴 JSON", '{"nutrients":[{"nutrient":"protein","direction":"high"},', None),
    ("JSON 아님", "죄송합니다. 답할 수 없습니다.", None),
    ("빈 응답", "", None),
]


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def save_json(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_sentences(path):
    """정답 열은 읽지 않는다."""
    with open(path, encoding="utf-8-sig") as f:
        return [{"상황ID": r["상황ID"], "입력 문장": r["입력 문장"], "말투 유형": r["말투 유형"]}
                for r in csv.DictReader(f) if r["상황ID"].strip()]


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def check_offline():
    # 프롬프트: ft_data 전체와 글자까지 같은지
    prompts = set()
    for name in ("train_sft.jsonl", "val_sft.jsonl"):
        with open(os.path.join(FT, "ft_data", name), encoding="utf-8") as f:
            prompts |= {json.loads(line)["messages"][0]["content"] for line in f}
    prompt_ok = prompts == {qp.SYSTEM_PROMPT}
    sha = hashlib.sha256(qp.SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    print(f"[프롬프트] ft_data 프롬프트 종류 {len(prompts)}개, 일치 {prompt_ok}, sha256 {sha}")
    if not prompt_ok or sha != qp.SYSTEM_PROMPT_SHA256:
        sys.exit("STOP: 시스템 프롬프트 불일치")

    budget = [{"문장": s, "기대": e, "결과": qp.extract_budget(s), "통과": qp.extract_budget(s) == e} for s, e in BUDGET_CASES]
    print(f"\n[예산 단위 테스트] {sum(x['통과'] for x in budget)}/{len(budget)}")
    for x in budget:
        print(f"  {'OK ' if x['통과'] else 'FAIL'} {x['문장']!r:32} 기대={x['기대']} 결과={x['결과']}")

    resp = []
    for name, raw, want in RESPONSE_CASES:
        got, reason = qp.parse_model_response(raw)
        resp.append({"경우": name, "기대": want, "결과": got, "이유": reason, "통과": got == want})
    print(f"\n[응답 변환] {sum(x['통과'] for x in resp)}/{len(resp)}")
    for x in resp:
        print(f"  {'OK ' if x['통과'] else 'FAIL'} {x['경우']}: {x['결과']} {x['이유'] or ''}")

    # 재시도 흐름: 생성 함수만 가짜로 바꿔 시험한다
    good, bad = RESPONSE_CASES[0][1], "잡글"
    flows = []
    original = qp._generate
    logging.disable(logging.CRITICAL)
    try:
        limit = qp.MAX_INPUT_CHARS
        for name, text, replies, want_calls, want_none in (("1차 성공", "5천원으로 먹을 거", [good], 1, False),
                                                           ("1차 실패면 재시도 없이 None", "5천원으로 먹을 거", [bad, good], 1, True),
                                                           (f"정확히 {limit}자는 처리", "가" * limit, [good], 1, False),
                                                           (f"{limit + 1}자는 모델 호출 없음", "가" * (limit + 1), [good], 0, True)):
            queue, calls = list(replies), []
            qp._generate = lambda t: (calls.append(t), queue.pop(0))[1]
            out = qp.parse_query(text)
            flows.append({"경우": name, "호출": len(calls), "결과": out, "통과": len(calls) == want_calls and (out is None) == want_none})

        def boom(_):
            raise RuntimeError("가짜 오류")

        qp._generate = boom
        flows.append({"경우": "생성 중 예외", "호출": 1, "결과": qp.parse_query("문장"), "통과": qp.parse_query("문장") is None})
        calls = []
        qp._generate = lambda t: calls.append(t)
        flows.append({"경우": "빈 입력은 모델 호출 없음", "호출": len(calls), "결과": [qp.parse_query(""), qp.parse_query(" \n\t"), qp.parse_query(None)],
                      "통과": not calls})
    finally:
        qp._generate = original
        logging.disable(logging.NOTSET)
    print(f"\n[재시도 흐름] {sum(x['통과'] for x in flows)}/{len(flows)}")
    for x in flows:
        print(f"  {'OK ' if x['통과'] else 'FAIL'} {x['경우']}: 호출 {x['호출']}번, 결과 {x['결과']}")

    # 실제 문장: 예산 포함 유형 전체 통계 + 20문장 표본
    train, dev = read_sentences(TRAIN_CSV), read_sentences(DEV_CSV)
    lengths = [len(r["입력 문장"]) for r in train + dev]
    print(f"\n[문장 길이] train+dev {len(lengths)}문장, 최대 {max(lengths)}자, {qp.MAX_INPUT_CHARS}자 초과 {sum(n > qp.MAX_INPUT_CHARS for n in lengths)}개")
    rng = random.Random(SEED)
    budget_rows = [dict(r, 출처=p, 예산=qp.extract_budget(r["입력 문장"])) for p, rows in (("train", train), ("dev", dev)) for r in rows
                   if r["말투 유형"] == "예산 포함"]
    sample = rng.sample([r for r in budget_rows if r["출처"] == "train"], 10) + rng.sample([r for r in budget_rows if r["출처"] == "dev"], 10)
    missed = [r["입력 문장"] for r in budget_rows if r["예산"] is None]
    other = [dict(r, 예산=qp.extract_budget(r["입력 문장"])) for r in train + dev if r["말투 유형"] != "예산 포함"]
    false_pos = [(r["입력 문장"], r["예산"]) for r in other if r["예산"] is not None]
    print(f"\n[예산 포함 유형 전체] {len(budget_rows)}문장, 금액 찾음 {len(budget_rows) - len(missed)}, 못 찾음 {len(missed)}")
    for s in missed:
        print("  미추출:", s)
    print(f"[다른 유형] {len(other)}문장 중 금액으로 잡힘 {len(false_pos)}")
    for s, v in false_pos:
        print(f"  {v}: {s}")
    print("\n[표본 20문장]")
    for r in sample:
        print(f"  {r['출처']:5} {str(r['예산']):>7} | {r['입력 문장']}")
    values = sorted(r["예산"] for r in budget_rows if r["예산"] is not None)
    print("\n금액 범위:", values[:5], "...", values[-5:])
    print("\n[해석이 모호한 문장: 넘/이상/짜리/어치/할인, 또는 금액 2개 이상의 후보]")
    ambiguous = [r for r in budget_rows if any(k in r["입력 문장"] for k in ("넘", "이상", "짜리", "어치", "할인", "남았", "썼"))]
    print(f"  {len(ambiguous)}문장")
    for r in ambiguous[:25]:
        print(f"  {r['예산']}: {r['입력 문장']}")
    save_json("offline.json", {"prompt_match": prompt_ok, "system_prompt_sha256": sha, "budget_cases": budget, "response_cases": resp, "flows": flows,
                               "budget_type_total": len(budget_rows), "budget_type_missed": missed, "other_type_total": len(other),
                               "other_type_false_positive": false_pos, "budget_sample_20": sample,
                               "ambiguous": [{"문장": r["입력 문장"], "예산": r["예산"]} for r in ambiguous]})
    ok = all(x["통과"] for x in budget + resp + flows)
    print("\n오프라인 전체 통과" if ok else "\n오프라인 실패 있음")
    return ok


def wait_for_gpu():
    while True:
        apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
        used = int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0])
        if not apps and used < 1000:
            print(f"GPU 사용 가능: {used} MiB 사용 중, 다른 작업 없음", flush=True)
            return
        print(f"[{time.strftime('%H:%M:%S')}] GPU 대기: {used} MiB, 작업 {apps or '없음'}", flush=True)
        time.sleep(60)


def check_gpu():
    wait_for_gpu()
    md5_before = {p: md5(p) for p in (TRAIN_CSV, DEV_CSV)}
    handler = ListHandler()
    logging.getLogger("query_parser").addHandler(handler)

    t0 = time.time()
    bundle = qp.load_model()
    load_sec = round(time.time() - t0, 1)
    cached = qp.load_model() is bundle
    print(f"[로딩] {bundle['adapter_path']} {load_sec}초, 캐시 재사용 {cached}", flush=True)
    import torch
    mem = round(torch.cuda.memory_allocated() / 2**30, 2)

    # 2. 전체 흐름: 상황별 3문장 (첫 호출 지연을 빼려고 예열 1번)
    qp.parse_query("예열")
    dev = read_sentences(DEV_CSV)
    with open(PREV_DEV_ROWS, encoding="utf-8-sig") as f:
        prev_raw = {r["입력 문장"]: r["raw_output"] for r in csv.DictReader(f)}
    rng = random.Random(SEED)
    picks = []
    for sid in sorted({r["상황ID"] for r in dev}):
        picks += rng.sample([r for r in dev if r["상황ID"] == sid], 3)
    flow = []
    print("\n[전체 흐름]", flush=True)
    for r in picks:
        n_log = len(handler.messages)
        t = time.time()
        out = qp.parse_query(r["입력 문장"])
        sec = time.time() - t
        raw = qp._generate(r["입력 문장"])  # 지난 평가 응답과 같은지 비교용
        flow.append({**r, "결과": out, "초": round(sec, 3), "로그": handler.messages[n_log:], "지난평가_응답일치": raw == prev_raw.get(r["입력 문장"])})
        print(f"  {r['상황ID']:6} {sec:5.2f}s {json.dumps(out, ensure_ascii=False)} | {r['입력 문장']}", flush=True)
    secs = [x["초"] for x in flow]
    n_ok = sum(x["결과"] is not None for x in flow)
    print(f"성공 {n_ok}/{len(flow)}, 평균 {statistics.mean(secs):.3f}초, 최대 {max(secs):.3f}초, 지난 평가 응답 일치 {sum(x['지난평가_응답일치'] for x in flow)}/{len(flow)}", flush=True)

    # 3. 엉뚱한 입력
    long_sentence = "오늘 회사에서 하루 종일 회의를 하고 나서 저녁에 집에 가는 길에 편의점에 들렀는데 뭘 먹어야 할지 모르겠어서 한참을 서 있었어요, " * 30 + "뭐가 좋을까요?"
    odd_inputs = [("빈 문자열", ""), ("공백", "   \n\t "), ("인사", "안녕하세요"), ("무관한 문장", "내일 서울에서 부산 가는 기차 시간 알려줘"),
                  (f"아주 긴 문장 {len(long_sentence)}자", long_sentence), ("무관+금액", "친구한테 3만원 빌렸는데 언제 갚지"),
                  ("매우 긴 입력 20만자 (안정성)", "가나다라마바사 " * 25000)]
    odd = []
    print("\n[엉뚱한 입력]", flush=True)
    for name, text in odd_inputs:
        n_log = len(handler.messages)
        t = time.time()
        out = qp.parse_query(text)
        odd.append({"입력": name, "결과": out, "초": round(time.time() - t, 3), "로그": [m[:200] for m in handler.messages[n_log:]]})
        print(f"  {name}: {json.dumps(out, ensure_ascii=False)} ({odd[-1]['초']}초) {odd[-1]['로그'][:1]}", flush=True)
    after_oom = qp.parse_query("5천원 이하로 운동 후에 먹을 거")
    print(f"  직후 정상 문장: {after_oom}", flush=True)

    # 4. 반복 일치
    repeat = []
    print("\n[반복 3번]", flush=True)
    for text in ("5천원 이하로 운동 후에 먹을 거", "야식으로 먹을 건데 2만원대로 짜지 않은 거", "요즘 혈당이 걱정돼요"):
        results = [qp.parse_query(text) for _ in range(3)]
        same = all(x == results[0] for x in results)
        repeat.append({"문장": text, "결과": results[0], "3번 일치": same})
        print(f"  {same} {json.dumps(results[0], ensure_ascii=False)} | {text}", flush=True)

    # 사용법 예시용
    examples = {s: qp.parse_query(s) for s in ("단백질 많은 걸로 1만5천원 안쪽에서 골라줘", "오천원으로 야식 먹을 건데 짠 건 싫어", "다이어트 시작했어요")}
    print("\n[예시]", json.dumps(examples, ensure_ascii=False, indent=1), flush=True)

    peak = round(torch.cuda.max_memory_allocated() / 2**30, 2)
    qp.unload_model()
    unchanged = all(md5(p) == h for p, h in md5_before.items())
    save_json("gpu.json", {"adapter": bundle["adapter_path"], "load_sec": load_sec, "cache_reused": cached, "mem_allocated_gib": mem, "peak_allocated_gib": peak,
                           "flow": flow, "flow_ok": n_ok, "flow_n": len(flow), "mean_sec": round(statistics.mean(secs), 3), "max_sec": max(secs),
                           "odd": odd, "after_long_input": after_oom, "repeat": repeat, "examples": examples, "inputs_md5_unchanged": unchanged})
    print(f"\n메모리 {mem} GiB, 최대 {peak} GiB, 입력 md5 변화 없음 {unchanged}, 모델 내림 완료", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "offline":
        sys.exit(0 if check_offline() else 1)
    elif mode == "gpu":
        check_gpu()
    else:
        sys.exit(__doc__)
