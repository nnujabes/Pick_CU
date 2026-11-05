"""QLoRA 시간·메모리 벤치마크 (본 학습 아님). train_sft.jsonl 앞부분으로 최대 20 optimizer step만 돈다.
마지막에 val 문장 몇 개로 4bit+LoRA 생성 속도를 잰다(채점 안 함). dev/test는 읽지 않는다.

usage: python bench_train.py <train_jsonl> <val_jsonl> <out_dir> [--steps 20] [--micro_bs 8] [--accum 2] [--gc 1]
"""
import argparse
import json
import math
import os
import random
import subprocess
import time

import torch

MODEL_ID = "skt/A.X-4.0-Light"
MODEL_REVISION = "ba21c20ea1b31ded1ec3e2fb432335077dc4be98"
SEED = 42
MAX_LEN = 384  # 실측 최대 333토큰 → 잘림 없음


def gpu_used_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip()
    return int(out.splitlines()[0])


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def encode(tok, rec):
    ids = tok.apply_chat_template(rec["messages"], tokenize=True, return_dict=True)["input_ids"][:MAX_LEN]
    n = rec["n_prompt_tokens"]
    labels = [-100] * n + ids[n:]
    return ids, labels


def collate(batch, pad_id):
    L = max(len(i) for i, _ in batch)
    ids = torch.full((len(batch), L), pad_id, dtype=torch.long)
    lab = torch.full((len(batch), L), -100, dtype=torch.long)
    att = torch.zeros((len(batch), L), dtype=torch.long)
    for k, (i, l) in enumerate(batch):
        ids[k, :len(i)] = torch.tensor(i)
        lab[k, :len(l)] = torch.tensor(l)
        att[k, :len(i)] = 1
    return ids, lab, att


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("train_jsonl")
    ap.add_argument("val_jsonl")
    ap.add_argument("out_dir")
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--micro_bs", type=int, default=8)
    ap.add_argument("--accum", type=int, default=2)
    ap.add_argument("--gc", type=int, default=1)
    ap.add_argument("--gen_n", type=int, default=16)
    a = ap.parse_args()
    assert a.steps <= 20, "벤치마크는 최대 20 step"
    os.makedirs(a.out_dir, exist_ok=True)

    import bitsandbytes
    import peft
    import transformers
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, get_cosine_schedule_with_warmup

    random.seed(SEED)
    torch.manual_seed(SEED)
    res = {"versions": {"torch": torch.__version__, "transformers": transformers.__version__, "peft": peft.__version__,
                        "bitsandbytes": bitsandbytes.__version__},
           "config": {"quant": "4bit NF4, double quant, compute bf16", "lora_r": 16, "lora_alpha": 32, "lora_dropout": 0.05,
                      "target": "all linear (q,k,v,o,gate,up,down)", "lr": 2e-4, "sched": "cosine, warmup 3%",
                      "micro_bs": a.micro_bs, "accum": a.accum, "effective_bs": a.micro_bs * a.accum,
                      "grad_checkpointing": bool(a.gc), "max_len": MAX_LEN, "optimizer": "torch AdamW (LoRA params)"},
           "gpu_used_before_mib": gpu_used_mib()}

    tok = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16)
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=MODEL_REVISION, quantization_config=bnb,
                                                 dtype=torch.bfloat16, device_map="cuda")
    res["load_4bit_sec"] = round(time.time() - t0, 1)
    res["mem_after_4bit_load_gib"] = round(torch.cuda.memory_allocated() / 2**30, 2)
    res["gpu_used_after_load_mib"] = gpu_used_mib()
    print("4bit loaded", res["mem_after_4bit_load_gib"], "GiB", flush=True)

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=bool(a.gc),
                                            gradient_checkpointing_kwargs={"use_reentrant": False})
    cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, cfg)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    res["trainable_params"] = trainable
    res["trainable_pct"] = round(100 * trainable / total, 3)
    model.config.use_cache = False

    train = load_jsonl(a.train_jsonl)
    random.shuffle(train)
    need = a.steps * a.micro_bs * a.accum
    data = [encode(tok, r) for r in train[:need]]
    planned_steps_3ep = math.ceil(len(train) / (a.micro_bs * a.accum)) * 3
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=2e-4, weight_decay=0.0)
    sch = get_cosine_schedule_with_warmup(opt, max(1, int(0.03 * planned_steps_3ep)), planned_steps_3ep)

    model.train()
    torch.cuda.reset_peak_memory_stats()
    step_times, step_tokens, losses = [], [], []
    i = 0
    for step in range(a.steps):
        torch.cuda.synchronize()
        ts = time.time()
        ntok, lsum = 0, 0.0
        for _ in range(a.accum):
            batch = data[i:i + a.micro_bs]
            i += a.micro_bs
            ids, lab, att = (x.cuda() for x in collate(batch, pad_id))
            out = model(input_ids=ids, attention_mask=att, labels=lab)
            (out.loss / a.accum).backward()
            ntok += int(att.sum())
            lsum += out.loss.item() / a.accum
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
        sch.step()
        opt.zero_grad(set_to_none=True)
        torch.cuda.synchronize()
        step_times.append(time.time() - ts)
        step_tokens.append(ntok)
        losses.append(round(lsum, 4))
        print(f"step {step+1}/{a.steps} {step_times[-1]:.2f}s tokens={ntok} loss={lsum:.4f}", flush=True)

    steady = step_times[2:] if len(step_times) > 4 else step_times
    steady_tok = step_tokens[2:] if len(step_tokens) > 4 else step_tokens
    res["train"] = {"steps": a.steps, "samples_per_step": a.micro_bs * a.accum,
                    "sec_per_step_all": [round(x, 2) for x in step_times],
                    "sec_per_step_steady_mean": round(sum(steady) / len(steady), 3),
                    "tokens_per_sec_steady": round(sum(steady_tok) / sum(steady), 1),
                    "loss": losses,
                    "peak_mem_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                    "peak_mem_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 2),
                    "gpu_used_after_train_mib": gpu_used_mib()}

    # 체크포인트(어댑터) 저장 용량
    ad = os.path.join(a.out_dir, "bench_adapter")
    model.save_pretrained(ad)
    res["adapter_size_mb"] = round(sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(ad) for f in fs) / 2**20, 1)

    # 생성 속도 (val 앞 gen_n문장, greedy, max_new_tokens 128, 채점 안 함)
    model.eval()
    model.config.use_cache = True
    val = load_jsonl(a.val_jsonl)[:a.gen_n]
    gts = []
    for r in val:
        enc = tok.apply_chat_template(r["messages"][:2], add_generation_prompt=True, return_tensors="pt",
                                      return_dict=True).to("cuda")
        torch.cuda.synchronize()
        ts = time.time()
        with torch.no_grad():
            model.generate(**enc, max_new_tokens=128, do_sample=False, pad_token_id=pad_id)
        torch.cuda.synchronize()
        gts.append(time.time() - ts)
    res["generate"] = {"n": len(gts), "sec_per_sentence_mean": round(sum(gts[1:]) / max(1, len(gts) - 1), 3),
                       "note": "4bit+LoRA, batch 1, greedy, max_new_tokens 128 (bf16 베이스라인은 216문장 142초 = 0.66초/문장)"}
    json.dump(res, open(os.path.join(a.out_dir, "bench_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()
