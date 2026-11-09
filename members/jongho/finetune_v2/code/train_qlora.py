"""A.X-4.0-Light QLoRA 학습 + epoch별 val 평가 + early stopping. 끝나면 best 어댑터로 dev를 한 번 평가.

- 학습: ft_data/train_sft.jsonl (85상황 2,550문장). 손실은 assistant 토큰만.
- 선택: ft_data/val_sft.jsonl (9상황 270문장), 기준 = val 완전 정답률(베이스라인과 같은 채점).
- dev: best epoch가 정해진 뒤 한 번만 평가. test는 열지 않는다.
- 모델 입력은 시스템 프롬프트 + 입력 문장뿐. 정답 열은 채점에만 쓴다.

usage: python train_qlora.py <ft_dir> <train_csv> <dev_csv> [--epochs 10] [--patience 3] [--lr 2e-4] [--r 16]
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import random
import shutil
import subprocess
import time

import torch

MODEL_ID = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"
MODEL_REVISION = "553ea250b9a5317231459279d5847d6cf955b9aa"
TRUST_REMOTE_CODE = True  # EXAONE 3.5는 모델에 딸린 코드(modeling_exaone.py)로 불러온다


TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "out_proj", "c_fc_0", "c_fc_1", "c_proj"]  # A.X의 q,k,v,o,gate,up,down에 해당


def fix_exaone_embeddings(model):
    """EXAONE 코드에 없는 임베딩 접근 함수를 채운다. gradient checkpointing에서 LoRA 학습 신호와 어댑터 저장에 필요하다."""
    inner = model.transformer
    type(inner).get_input_embeddings = lambda self: self.wte
    type(inner).set_input_embeddings = lambda self, v: setattr(self, "wte", v)
    type(model).get_input_embeddings = lambda self: self.transformer.wte
    type(model).get_output_embeddings = lambda self: self.lm_head
    return model
SEED = 42
MAX_LEN = 384
EXPECTED_SYS_SHA = "06818f0f2ba2c5ac7f05454846c37e9054766184d62cd521b6afe0eab479b556"

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("base", os.path.join(HERE, "dev_pair_baseline.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def gpu_used_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip()
    return int(out.splitlines()[0])


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def chat_ids(tok, msgs):
    """질문 토큰 + 답 토큰. EXAONE은 [|assistant|]가 일반 글자라 답 첫 글자와 토큰이 붙으므로 따로 토큰화한다.
    학습하는 글자는 v1과 같다(전체 대화에서 질문 부분을 뺀 나머지)."""
    p_txt = tok.apply_chat_template(msgs[:2], add_generation_prompt=True, tokenize=False)
    f_txt = tok.apply_chat_template(msgs, tokenize=False)
    assert f_txt.startswith(p_txt), "prompt text prefix mismatch"
    p_ids = tok.apply_chat_template(msgs[:2], add_generation_prompt=True, tokenize=True, return_dict=True)["input_ids"]
    a_ids = tok(f_txt[len(p_txt):], add_special_tokens=False)["input_ids"]
    return p_ids, p_ids + a_ids


def encode(tok, rec):
    ids = chat_ids(tok, rec["messages"])[1][:MAX_LEN]
    n = rec["n_prompt_tokens"]
    return ids, [-100] * n + ids[n:]


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


@torch.no_grad()
def val_loss(model, data, pad_id, bs=8):
    model.eval()
    tot, n = 0.0, 0
    for i in range(0, len(data), bs):
        ids, lab, att = (x.cuda() for x in collate(data[i:i + bs], pad_id))
        out = model(input_ids=ids, attention_mask=att, labels=lab)
        k = int((lab[:, 1:] != -100).sum())
        tot += out.loss.item() * k
        n += k
    return tot / n


@torch.no_grad()
def generate_eval(model, tok, rows, eos_ids, pad_id, tag):
    """베이스라인과 같은 방식: 문장 하나씩, greedy, max_new_tokens 128, 입력 문장만."""
    model.eval()
    model.config.use_cache = True
    out_rows = []
    t0 = time.time()
    for i, r in enumerate(rows):
        enc = tok.apply_chat_template(base.build_messages(r["입력 문장"]), add_generation_prompt=True,
                                      return_tensors="pt", return_dict=True).to("cuda")
        out = model.generate(**enc, max_new_tokens=base.MAX_NEW_TOKENS, do_sample=False, pad_token_id=pad_id)
        new = out[0][enc["input_ids"].shape[1]:]
        text = tok.decode(new, skip_special_tokens=True)
        items, parse_ok, schema_ok = base.parse_output(text)
        out_rows.append({"row": i + 1, **r, "raw_output": text, "items": items, "parse_ok": parse_ok,
                         "schema_ok": schema_ok, "truncated": int(new[-1]) not in eos_ids,
                         **base.score(r["gold1"], r["gold2"], items)})
        if (i + 1) % 54 == 0 or i + 1 == len(rows):
            log(f"  {tag} gen [{i+1}/{len(rows)}] exact={sum(x['exact'] for x in out_rows)} {time.time()-t0:.0f}s")
    model.config.use_cache = False
    return out_rows, round(time.time() - t0, 1)


def save_eval(rows, out_dir, extra):
    os.makedirs(out_dir, exist_ok=True)
    s = {**extra, "n": len(rows), "prompt_fields_used": ["입력 문장"], **base.summarize(rows)}
    json.dump(s, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    base.write_rows(rows, os.path.join(out_dir, "rows.csv"))
    base.write_rows(rows, os.path.join(out_dir, "wrong.csv"), only_wrong=True)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ft_dir")
    ap.add_argument("train_csv")
    ap.add_argument("dev_csv")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--patience", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--r", type=int, default=16)
    ap.add_argument("--micro_bs", type=int, default=8)
    ap.add_argument("--accum", type=int, default=2)
    ap.add_argument("--run", default="run_r16_lr2e-4")
    ap.add_argument("--smoke", type=int, default=0, help="1이면 흐름 점검만: epoch당 2 step, val 6문장, dev 4문장")
    a = ap.parse_args()

    import peft
    import transformers
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, get_cosine_schedule_with_warmup

    run_dir = os.path.join(a.ft_dir, "ckpt", a.run)
    res_dir = os.path.join(a.ft_dir, "results", a.run)
    os.makedirs(run_dir, exist_ok=False)  # 기존 실행 덮어쓰기 방지
    os.makedirs(res_dir, exist_ok=False)
    random.seed(SEED)
    torch.manual_seed(SEED)

    assert hashlib.sha256(base.SYSTEM_PROMPT.encode("utf-8")).hexdigest() == EXPECTED_SYS_SHA, "system prompt mismatch"
    info = json.load(open(os.path.join(a.ft_dir, "ft_data", "data_info.json"), encoding="utf-8"))
    val_sits = set(info["val_situations"])
    md5_in = {"train_csv": md5(a.train_csv), "dev_csv": md5(a.dev_csv)}

    # 채점용 정답 (val은 train_csv에서 val 상황만, 같은 순서)
    val_rows = [r for r in base.read_dev(a.train_csv) if r["상황ID"] in val_sits]
    assert len(val_rows) == 270, len(val_rows)
    train_recs = load_jsonl(os.path.join(a.ft_dir, "ft_data", "train_sft.jsonl"))
    val_recs = load_jsonl(os.path.join(a.ft_dir, "ft_data", "val_sft.jsonl"))
    assert len(train_recs) == 2550 and len(val_recs) == 270
    assert not ({x["상황ID"] for x in train_recs} & val_sits)

    others = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
                            capture_output=True, text=True).stdout.strip()
    log(f"GPU used {gpu_used_mib()} MiB, other compute apps: {others or 'none'}")

    tok = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=TRUST_REMOTE_CODE)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=TRUST_REMOTE_CODE, quantization_config=bnb,
                                                 dtype=torch.bfloat16, device_map="cuda")
    eos = model.generation_config.eos_token_id
    eos_ids = set(eos if isinstance(eos, list) else [eos]) | {tok.eos_token_id}
    fix_exaone_embeddings(model)
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                            gradient_checkpointing_kwargs={"use_reentrant": False})
    lcfg = LoraConfig(r=a.r, lora_alpha=2 * a.r, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=TARGET_MODULES)
    model = get_peft_model(model, lcfg)
    model.config.use_cache = False
    params = [p for p in model.parameters() if p.requires_grad]

    train_data = [encode(tok, r) for r in train_recs]
    val_data = [encode(tok, r) for r in val_recs]
    eff = a.micro_bs * a.accum
    steps_per_epoch = math.ceil(len(train_data) / eff)
    if a.smoke:
        steps_per_epoch = 2
        val_rows, val_data = val_rows[:6], val_data[:8]
    total_steps = steps_per_epoch * a.epochs
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.0)
    sch = get_cosine_schedule_with_warmup(opt, max(1, int(0.03 * total_steps)), total_steps)

    config = {"model": MODEL_ID, "revision": MODEL_REVISION, "quant": "4bit NF4 double-quant, compute bf16",
              "lora": {"r": a.r, "alpha": 2 * a.r, "dropout": 0.05, "target": TARGET_MODULES},
              "lr": a.lr, "sched": "cosine, warmup 3% of max steps", "max_epochs": a.epochs,
              "early_stopping": {"metric": "val exact (sentence)", "patience": a.patience, "rule": "개선 없는 epoch가 patience번 연속이면 중단"},
              "micro_bs": a.micro_bs, "accum": a.accum, "effective_bs": eff, "steps_per_epoch": steps_per_epoch,
              "max_len": MAX_LEN, "grad_checkpointing": True, "seed": SEED,
              "versions": {"torch": torch.__version__, "transformers": transformers.__version__, "peft": peft.__version__},
              "inputs_md5": md5_in, "system_prompt_sha256": EXPECTED_SYS_SHA,
              "val_situations": sorted(val_sits), "dev_eval": "best epoch 확정 후 1회"}
    json.dump(config, open(os.path.join(res_dir, "config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log(f"start: {steps_per_epoch} steps/epoch, max {a.epochs} epochs, patience {a.patience}")

    history, best, bad = [], None, 0
    hist_path = os.path.join(res_dir, "history.jsonl")
    t_start = time.time()
    for ep in range(1, a.epochs + 1):
        model.train()
        order = list(range(len(train_data)))
        random.Random(SEED + ep).shuffle(order)
        te = time.time()
        losses = []
        for s in range(steps_per_epoch):
            idx = order[s * eff:(s + 1) * eff]
            lsum = 0.0
            for m in range(0, len(idx), a.micro_bs):
                batch = [train_data[j] for j in idx[m:m + a.micro_bs]]
                ids, lab, att = (x.cuda() for x in collate(batch, pad_id))
                out = model(input_ids=ids, attention_mask=att, labels=lab)
                frac = len(batch) / len(idx)
                (out.loss * frac).backward()
                lsum += out.loss.item() * frac
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            sch.step()
            opt.zero_grad(set_to_none=True)
            losses.append(lsum)
            if (s + 1) % 40 == 0 or s + 1 == steps_per_epoch:
                log(f"ep{ep} step {s+1}/{steps_per_epoch} loss={sum(losses[-40:])/len(losses[-40:]):.4f} lr={sch.get_last_lr()[0]:.2e}")
        train_sec = round(time.time() - te, 1)

        vl = val_loss(model, val_data, pad_id)
        rows, gen_sec = generate_eval(model, tok, val_rows, eos_ids, pad_id, f"ep{ep} val")
        ov = base.overall(rows)
        ad_dir = os.path.join(run_dir, f"epoch_{ep:02d}")
        model.save_pretrained(ad_dir)
        save_eval(rows, os.path.join(res_dir, f"val_epoch_{ep:02d}"), {"epoch": ep, "split": "train-internal val (9 situations)"})
        rec = {"epoch": ep, "train_loss_mean": round(sum(losses) / len(losses), 5), "val_loss": round(vl, 5),
               "val_exact": ov["exact"], "val_pair": ov["pair"], "val_first": ov["first"], "val_second": ov["second"],
               "train_sec": train_sec, "val_gen_sec": gen_sec, "peak_mem_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 2),
               "elapsed_min": round((time.time() - t_start) / 60, 1)}
        improved = best is None or ov["exact"]["correct"] > best["val_exact"]["correct"]
        if improved:
            best, bad = rec, 0
        else:
            bad += 1
        rec["best_so_far"] = best["epoch"]
        rec["no_improve_count"] = bad
        history.append(rec)
        with open(hist_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log(f"EPOCH {ep} done: train_loss={rec['train_loss_mean']} val_loss={rec['val_loss']} "
            f"val_exact={ov['exact']['correct']}/{len(val_rows)} best=ep{best['epoch']} no_improve={bad}/{a.patience}")
        if bad >= a.patience:
            log(f"EARLY STOP at epoch {ep} (best epoch {best['epoch']})")
            break

    stopped = "early_stop" if bad >= a.patience else "max_epochs"
    best_dir = os.path.join(run_dir, f"epoch_{best['epoch']:02d}")
    shutil.copytree(best_dir, os.path.join(run_dir, "best"))
    log(f"best = epoch {best['epoch']} ({best['val_exact']['correct']}/270). dev 평가 1회 시작")

    # dev: best 어댑터로 1회
    del model
    torch.cuda.empty_cache()
    from peft import PeftModel
    bm = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=TRUST_REMOTE_CODE, quantization_config=bnb,
                                              dtype=torch.bfloat16, device_map="cuda")
    fix_exaone_embeddings(bm)
    model = PeftModel.from_pretrained(bm, os.path.join(run_dir, "best"))
    dev_rows = base.read_dev(a.dev_csv)
    assert len(dev_rows) == 216
    if a.smoke:  # 흐름 점검에서는 dev 대신 val 문장을 쓴다 (dev는 본 실행에서 1회만)
        dev_rows = val_rows[:4]
    rows, dev_sec = generate_eval(model, tok, dev_rows, eos_ids, pad_id, "dev(best)")
    dev_s = save_eval(rows, os.path.join(res_dir, "dev_best"),
                      {"epoch": best["epoch"], "split": "dev_pair_v3 (216)", "dev_md5": md5(a.dev_csv),
                       "model": "A.X-4.0-Light 4bit NF4 + LoRA best adapter", "fine_tuned": True})

    final = {"run": a.run, "stopped": stopped, "epochs_run": len(history), "best_epoch": best["epoch"],
             "best_val": best, "dev_best": {"exact": dev_s["overall"]["exact"], "pair": dev_s["overall"]["pair"],
                                           "first": dev_s["overall"]["first"], "second": dev_s["overall"]["second"],
                                           "gen_sec": dev_sec},
             "baseline_dev_exact": "94/216 = 43.5% (bf16, prompt only)",
             "total_min": round((time.time() - t_start) / 60, 1),
             "inputs_md5_unchanged": {"train_csv": md5(a.train_csv) == md5_in["train_csv"], "dev_csv": md5(a.dev_csv) == md5_in["dev_csv"]}}
    json.dump(final, open(os.path.join(res_dir, "final_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log("FINAL " + json.dumps(final, ensure_ascii=False))


if __name__ == "__main__":
    main()
