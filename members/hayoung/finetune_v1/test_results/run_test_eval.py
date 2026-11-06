"""WSL 최종 test 측정: run_dev_check.py를 복사해 입력 경로, 출력 폴더, 어댑터 스위치(USE_ADAPTER)만 바꿨다.
생성/프롬프트/파싱/채점은 train_qlora.py, dev_pair_baseline.py를 그대로 쓴다. 실행마다 1회만 (출력 폴더가 있으면 멈춘다)."""
import hashlib, importlib.util, json, os, subprocess, sys, time
import csv, random  # 추가: 문장별 즉시 저장(rows_partial.csv), seed 42
CODE = os.path.expanduser("~/work/finetune_v1/code")
ADAPTER = os.path.expanduser("~/work/finetune_v1/adapter/best")
TEST = os.path.expanduser("~/work/test_eval/test_pair_v3_240.csv")
USE_ADAPTER = os.environ["USE_ADAPTER"] == "1"
OUT = os.path.expanduser("~/work/test_eval/ft" if USE_ADAPTER else "~/work/test_eval/base4bit")
os.makedirs(OUT, exist_ok=False)  # 같은 측정을 두 번 하지 않도록 기존 폴더가 있으면 멈춘다

spec = importlib.util.spec_from_file_location("train_qlora", os.path.join(CODE, "train_qlora.py"))
tq = importlib.util.module_from_spec(spec); spec.loader.exec_module(tq)
base = tq.base
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

log = tq.log
random.seed(tq.SEED); torch.manual_seed(tq.SEED)  # seed 42 (greedy라 결과에는 영향 없음)
sha = hashlib.sha256(base.SYSTEM_PROMPT.encode("utf-8")).hexdigest()
assert sha == tq.EXPECTED_SYS_SHA, f"system prompt mismatch {sha}"
test_md5 = tq.md5(TEST)
assert test_md5 == "a405dcd384aa8f5777eea5add5cc1795", test_md5
log(f"sys sha256 {sha} OK, test md5 {test_md5}, USE_ADAPTER={int(USE_ADAPTER)}, seed {tq.SEED}")
log(f"GPU used {tq.gpu_used_mib()} MiB")
t_all = time.time()
tok = AutoTokenizer.from_pretrained(tq.MODEL_ID, revision=tq.MODEL_REVISION)
pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                         bnb_4bit_compute_dtype=torch.bfloat16)
bm = AutoModelForCausalLM.from_pretrained(tq.MODEL_ID, revision=tq.MODEL_REVISION, quantization_config=bnb,
                                          dtype=torch.bfloat16, device_map="cuda")
eos = bm.generation_config.eos_token_id
eos_ids = set(eos if isinstance(eos, list) else [eos]) | {tok.eos_token_id}
model = PeftModel.from_pretrained(bm, ADAPTER) if USE_ADAPTER else bm
load_sec = round(time.time() - t_all, 1)
log(f"model loaded (adapter={int(USE_ADAPTER)}) {load_sec}s, GPU used {tq.gpu_used_mib()} MiB, peak alloc {torch.cuda.max_memory_allocated()/2**30:.2f} GiB")
test_rows = base.read_dev(TEST)
assert len(test_rows) == 240

# 추가: 문장별 즉시 저장. generate_eval은 문장마다 parse_output을 정확히 한 번, 순서대로 부른다.
# 원래 함수의 반환값을 그대로 돌려주고, 같은 score()로 채점한 결과를 한 줄씩 기록만 한다.
_orig_parse = base.parse_output
_pf = open(os.path.join(OUT, "rows_partial.csv"), "w", encoding="utf-8-sig", newline="")
_pw = csv.writer(_pf)
_pw.writerow(["row", "상황ID", "말투 유형", "입력 문장", "정답1", "정답2", "raw_output", "items", "parse_ok", "schema_ok", "exact"])
_k = [0]


def _parse_and_record(text):
    res = _orig_parse(text)
    r = test_rows[_k[0]]
    sc = base.score(r["gold1"], r["gold2"], res[0])
    _pw.writerow([_k[0] + 1, r["상황ID"], r["말투 유형"], r["입력 문장"], "/".join(r["gold1"]), "/".join(r["gold2"]),
                  text, json.dumps(res[0], ensure_ascii=False), res[1], res[2], sc["exact"]])
    _pf.flush(); os.fsync(_pf.fileno())
    _k[0] += 1
    return res


base.parse_output = _parse_and_record

tag = "test(ft)" if USE_ADAPTER else "test(base4bit)"
rows, test_sec = tq.generate_eval(model, tok, test_rows, eos_ids, pad_id, tag)
_pf.close()
assert _k[0] == 240, _k[0]
s = tq.save_eval(rows, OUT, {"split": "test_pair_v3_240 (240)", "test_md5": test_md5,
                             "adapter": ADAPTER if USE_ADAPTER else None, "use_adapter": USE_ADAPTER,
                             "model": "A.X-4.0-Light 4bit NF4" + (" + LoRA best adapter" if USE_ADAPTER else " (어댑터 없음)") + " (WSL RTX 4060)",
                             "load_sec": load_sec, "gen_sec": test_sec,
                             "peak_alloc_gib": round(torch.cuda.max_memory_allocated()/2**30, 2),
                             "test_md5_unchanged": tq.md5(TEST) == test_md5})
log(f"DONE exact={s['overall']['exact']} total {time.time()-t_all:.0f}s")
