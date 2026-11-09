"""EXAONE 학습 전 점검: 대화 형식, 질문 부분 일치(prefix), 끝 토큰, 4bit 로딩, LoRA를 붙일 층 이름.

usage: python check_model.py <out_json>
"""
import collections
import json
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from train_qlora import MODEL_ID, MODEL_REVISION, TRUST_REMOTE_CODE, chat_ids


def main(out_json):
    res = {"model": MODEL_ID, "revision": MODEL_REVISION}
    tok = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=TRUST_REMOTE_CODE)
    msgs = [{"role": "system", "content": "시스템"}, {"role": "user", "content": "운동 후에 먹을 거"},
            {"role": "assistant", "content": '{"nutrients": []}'}]
    prompt = tok.apply_chat_template(msgs[:2], add_generation_prompt=True, tokenize=False)
    full = tok.apply_chat_template(msgs, tokenize=False)
    p_ids, f_ids = chat_ids(tok, msgs)
    res.update(prompt_render=prompt, full_render=full, prefix_ok=f_ids[:len(p_ids)] == p_ids,
               eos_token=tok.eos_token, pad_token=tok.pad_token,
               ends_with_eos=f_ids[-1] == tok.convert_tokens_to_ids(tok.eos_token) or full.rstrip().endswith(tok.eos_token))
    print(json.dumps({k: res[k] for k in ("prefix_ok", "eos_token", "pad_token", "ends_with_eos")}, ensure_ascii=False), flush=True)

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=TRUST_REMOTE_CODE,
                                                 quantization_config=bnb, dtype=torch.bfloat16, device_map="cuda")
    names = collections.Counter(n.split(".")[-1] for n, m in model.named_modules()
                                if m.__class__.__name__ in ("Linear", "Linear4bit"))
    res.update(model_class=model.__class__.__name__, linear_layers=dict(names),
               mem_4bit_gib=round(torch.cuda.memory_allocated() / 2**30, 2),
               generation_eos=model.generation_config.eos_token_id)
    enc = tok.apply_chat_template(msgs[:2], add_generation_prompt=True, return_tensors="pt", return_dict=True).to("cuda")
    out = model.generate(**enc, max_new_tokens=32, do_sample=False)
    res["sample_output"] = tok.decode(out[0][enc["input_ids"].shape[1]:])
    print(json.dumps({k: res[k] for k in ("model_class", "linear_layers", "mem_4bit_gib", "generation_eos", "sample_output")},
                     ensure_ascii=False), flush=True)
    json.dump(res, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not (res["prefix_ok"] and res["ends_with_eos"]):
        sys.exit("STOP: 대화 형식 점검 실패")


if __name__ == "__main__":
    main(sys.argv[1])
