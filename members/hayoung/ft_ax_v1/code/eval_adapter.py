"""저장된 QLoRA 어댑터로 dev(또는 다른 CSV)를 평가한다. 학습은 하지 않는다.
train_qlora.py의 dev 평가 부분과 같은 방식: 4bit NF4 + LoRA, 문장 하나씩, greedy, max_new_tokens 128, 입력 문장만 모델에 넣음.

usage: python eval_adapter.py <adapter_dir> <csv> <out_dir>
예:    python eval_adapter.py ../ckpt/run_r16_lr2e-4/best ../../data/dev_pair_v3.csv ../results/reeval_dev
"""
import hashlib
import importlib.util
import json
import os
import random
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("tq", os.path.join(HERE, "train_qlora.py"))
tq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tq)
base = tq.base


def main(adapter_dir, csv_path, out_dir):
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    random.seed(tq.SEED)
    torch.manual_seed(tq.SEED)
    assert hashlib.sha256(base.SYSTEM_PROMPT.encode("utf-8")).hexdigest() == tq.EXPECTED_SYS_SHA, "system prompt mismatch"
    md5_before = tq.md5(csv_path)
    rows_in = base.read_dev(csv_path)
    tq.log(f"csv={csv_path} n={len(rows_in)} md5={md5_before}")

    tok = AutoTokenizer.from_pretrained(tq.MODEL_ID, revision=tq.MODEL_REVISION)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16)
    bm = AutoModelForCausalLM.from_pretrained(tq.MODEL_ID, revision=tq.MODEL_REVISION, quantization_config=bnb,
                                              dtype=torch.bfloat16, device_map="cuda")
    eos = bm.generation_config.eos_token_id
    eos_ids = set(eos if isinstance(eos, list) else [eos]) | {tok.eos_token_id}
    model = PeftModel.from_pretrained(bm, adapter_dir)
    rows, sec = tq.generate_eval(model, tok, rows_in, eos_ids, pad_id, "eval")
    s = tq.save_eval(rows, out_dir, {"adapter": os.path.abspath(adapter_dir), "csv": csv_path, "csv_md5": md5_before,
                                     "model": "A.X-4.0-Light 4bit NF4 + LoRA", "fine_tuned": True, "gen_sec": sec,
                                     "csv_md5_unchanged": tq.md5(csv_path) == md5_before})
    ex = s["overall"]["exact"]
    tq.log(f"done exact={ex['correct']}/{ex['n']} = {ex['acc']:.1%} -> {out_dir}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
