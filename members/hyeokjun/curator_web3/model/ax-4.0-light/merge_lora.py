"""A.X-4.0-Light 원본(bf16)에 LoRA 어댑터를 층별로 더해 merge한다.

메모리를 아끼려고 원본 조각을 텐서 단위로 읽고, 출력은 약 2GB씩 나눠 쓴다.
W_merged = W + (lora_alpha / r) * (B @ A)   # PEFT LoRA와 같은 식 (rslora·dora 꺼짐)
"""
import json
import os
import shutil
from glob import glob

import torch
from safetensors import safe_open
from safetensors.torch import save_file

BASE = os.path.expanduser(
    "~/.cache/huggingface/hub/models--skt--A.X-4.0-Light/snapshots/ba21c20ea1b31ded1ec3e2fb432335077dc4be98"
)
ADAPTER = os.path.expanduser("~/Daive-LLM/pickcu/members/hayoung/finetune_v1/adapter/best")
OUT = os.path.expanduser("~/pickcu_gguf/merged")
CHUNK_BYTES = 2 * 1024**3
torch.set_num_threads(8)

cfg = json.load(open(os.path.join(ADAPTER, "adapter_config.json")))
assert cfg["peft_type"] == "LORA" and not cfg["use_dora"] and not cfg["use_rslora"]
scale = cfg["lora_alpha"] / cfg["r"]
print(f"scale={scale}, r={cfg['r']}, targets={sorted(cfg['target_modules'])}", flush=True)

lora = {}
with safe_open(os.path.join(ADAPTER, "adapter_model.safetensors"), "pt") as f:
    for key in f.keys():
        module = key.removeprefix("base_model.model.").rsplit(".lora_", 1)[0]
        part = "A" if ".lora_A." in key else "B"
        lora.setdefault(module + ".weight", {})[part] = f.get_tensor(key)
print(f"LoRA 대상 가중치 {len(lora)}개", flush=True)

os.makedirs(OUT, exist_ok=True)
for name in os.listdir(BASE):
    path = os.path.join(BASE, name)
    if os.path.isfile(path) and not name.endswith(".safetensors") and name != "model.safetensors.index.json":
        shutil.copy(path, OUT)

weight_map, buffer, size, parts, merged = {}, {}, 0, [], 0


def flush():
    global buffer, size
    if not buffer:
        return
    fname = f"model-{len(parts) + 1:05d}.safetensors"
    save_file(buffer, os.path.join(OUT, fname), metadata={"format": "pt"})
    parts.append(fname)
    weight_map.update({key: fname for key in buffer})
    print(f"  저장 {fname} ({size / 1024**3:.2f}GB, 텐서 {len(buffer)}개)", flush=True)
    buffer, size = {}, 0


for shard in sorted(glob(os.path.join(BASE, "model-*.safetensors"))):
    print(f"읽는 중 {os.path.basename(shard)}", flush=True)
    with safe_open(shard, "pt") as f:
        for key in f.keys():
            weight = f.get_tensor(key)
            pair = lora.pop(key, None)
            if pair is not None:
                delta = pair["B"].float() @ pair["A"].float()
                assert delta.shape == weight.shape, (key, delta.shape, weight.shape)
                weight = (weight.float() + scale * delta).to(torch.bfloat16)
                merged += 1
            buffer[key] = weight.contiguous()
            size += weight.numel() * weight.element_size()
            if size >= CHUNK_BYTES:
                flush()
flush()

assert not lora, f"원본에서 찾지 못한 LoRA 대상: {list(lora)[:5]}"
total = sum(os.path.getsize(os.path.join(OUT, p)) for p in parts)
with open(os.path.join(OUT, "model.safetensors.index.json"), "w") as fp:
    json.dump({"metadata": {"total_size": total}, "weight_map": weight_map}, fp, indent=2)
print(f"완료: merge {merged}개, 파일 {len(parts)}개, {total / 1024**3:.2f}GB", flush=True)
