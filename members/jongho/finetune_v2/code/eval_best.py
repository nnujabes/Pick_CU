"""EXAONE best 어댑터로 dev와 test를 한 번씩 평가한다. 모델 로딩·생성·채점은 train_qlora.py와 같은 함수를 쓴다.

usage: python code/eval_best.py <adapter_dir> <dev_csv> <test_csv> <out_dir>
결과 폴더가 이미 있으면 멈춘다(test는 1회만 평가).
"""
import json
import os
import random
import sys

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_qlora as tq  # noqa: E402

adapter, dev_csv, test_csv, out = sys.argv[1:5]
os.makedirs(out, exist_ok=False)
base = tq.base
random.seed(tq.SEED); torch.manual_seed(tq.SEED)
md5_in = {"dev": tq.md5(dev_csv), "test": tq.md5(test_csv)}
tq.log(f"adapter={adapter} md5={md5_in}")

tok = AutoTokenizer.from_pretrained(tq.MODEL_ID, revision=tq.MODEL_REVISION, trust_remote_code=tq.TRUST_REMOTE_CODE)
pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                         bnb_4bit_compute_dtype=torch.bfloat16)
bm = AutoModelForCausalLM.from_pretrained(tq.MODEL_ID, revision=tq.MODEL_REVISION, trust_remote_code=tq.TRUST_REMOTE_CODE,
                                          quantization_config=bnb, dtype=torch.bfloat16, device_map="cuda")
eos = bm.generation_config.eos_token_id
eos_ids = set(eos if isinstance(eos, list) else [eos]) | {tok.eos_token_id}
tq.fix_exaone_embeddings(bm)
model = PeftModel.from_pretrained(bm, adapter)
model.eval()

summary = {}
for split, path, n in (("dev", dev_csv, 216), ("test", test_csv, 240)):
    rows_in = base.read_dev(path)
    assert len(rows_in) == n, (split, len(rows_in))
    rows, sec = tq.generate_eval(model, tok, rows_in, eos_ids, pad_id, split)
    s = tq.save_eval(rows, os.path.join(out, split), {
        "split": f"{split} ({n})", "csv_md5": md5_in[split], "adapter": adapter,
        "model": f"{tq.MODEL_ID} 4bit NF4 + LoRA best adapter", "fine_tuned": True, "gen_sec": sec})
    summary[split] = {"exact": s["overall"]["exact"], "pair": s["overall"]["pair"], "gen_sec": sec}
    tq.log(f"{split}: {json.dumps(summary[split], ensure_ascii=False)}")
summary["md5_unchanged"] = {k: tq.md5(p) == md5_in[k] for k, p in (("dev", dev_csv), ("test", test_csv))}
json.dump(summary, open(os.path.join(out, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
tq.log("EVAL_DONE " + json.dumps(summary, ensure_ascii=False))
