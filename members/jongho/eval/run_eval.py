"""파인튜닝 어댑터로 CSV를 평가한다. 채점과 저장은 hayoung/finetune_v1/code의 기존 코드를 그대로 쓴다.

실행 (저장소 루트에서):
    python members/jongho/eval/run_eval.py members/hayoung/dev_pair_v3_baseline/dev_pair_v3.csv members/jongho/eval/results/dev_new

결과 폴더가 이미 있으면 실행하지 않는다. test는 한 번만 평가해야 하기 때문이다.
모델에는 입력 문장만 넣는다.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FINETUNE_DIR = REPO_ROOT / "members" / "hayoung" / "finetune_v1"
CODE_DIR = FINETUNE_DIR / "code"
DEFAULT_ADAPTER = FINETUNE_DIR / "adapter" / "best"
DEFAULT_EXCLUDE = ("S3003",)  # 전체 점수에 포함하되, 이 상황을 뺀 점수도 함께 낸다.


def load_train_module():
    spec = importlib.util.spec_from_file_location("train_qlora", CODE_DIR / "train_qlora.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def accuracy(rows):
    """완전 정답률과 95% 구간(Wilson). 같은 상황의 문장을 독립으로 보므로 실제 불확실성은 더 크다."""
    n = len(rows)
    correct = sum(row["exact"] for row in rows)
    if not n:
        return {"correct": 0, "n": 0, "acc": None, "ci95": None}
    z, p = 1.96, correct / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {"correct": correct, "n": n, "acc": round(p, 4),
            "ci95": [round(center - margin, 4), round(center + margin, 4)]}


def build_report(rows, label, exclude=DEFAULT_EXCLUDE):
    """전체, 라벨 짝별, 지정 상황 제외 정답률. 지정 상황이 CSV에 없으면 excluding은 None이다."""
    pairs = {}
    for row in rows:
        pairs.setdefault(label(row), []).append(row)
    found = sorted({row["상황ID"] for row in rows} & set(exclude))
    kept = [row for row in rows if row["상황ID"] not in exclude]
    return {
        "overall": accuracy(rows),
        "by_pair": {name: accuracy(items) for name, items in sorted(pairs.items())},
        "excluding": {"situations": found, **accuracy(kept)} if found else None,
    }


def print_report(report):
    def line(name, value):
        print(f"{name}: {value['correct']}/{value['n']} = {value['acc']:.1%} (95% 구간 {value['ci95'][0]:.1%}~{value['ci95'][1]:.1%})")

    line("전체", report["overall"])
    if report["excluding"]:
        line(f"{','.join(report['excluding']['situations'])} 제외", report["excluding"])
    for name, value in report["by_pair"].items():
        line(name, value)


def run_eval(csv_path, out_dir, adapter_dir=DEFAULT_ADAPTER, exclude=DEFAULT_EXCLUDE):
    """CSV 전체를 평가해 out_dir에 summary.json, rows.csv, wrong.csv, report.json을 저장하고 report를 돌려준다."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise FileExistsError(f"결과 폴더가 이미 있습니다: {out_dir}")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tq = load_train_module()
    base = tq.base
    system_sha = hashlib.sha256(base.SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    if system_sha != tq.EXPECTED_SYS_SHA:
        raise RuntimeError(f"시스템 프롬프트가 학습 때와 다릅니다: {system_sha}")

    random.seed(tq.SEED)
    torch.manual_seed(tq.SEED)
    md5_before = file_md5(csv_path)
    rows_in = base.read_dev(str(csv_path))
    tq.log(f"csv={csv_path} n={len(rows_in)} md5={md5_before}")

    tokenizer = AutoTokenizer.from_pretrained(tq.MODEL_ID, revision=tq.MODEL_REVISION)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                                      bnb_4bit_compute_dtype=torch.bfloat16)
    base_model = AutoModelForCausalLM.from_pretrained(tq.MODEL_ID, revision=tq.MODEL_REVISION,
                                                      quantization_config=quantization, dtype=torch.bfloat16,
                                                      device_map="cuda")
    eos = base_model.generation_config.eos_token_id
    eos_ids = set(eos if isinstance(eos, list) else [eos]) | {tokenizer.eos_token_id}
    model = PeftModel.from_pretrained(base_model, str(adapter_dir))

    rows, seconds = tq.generate_eval(model, tokenizer, rows_in, eos_ids, pad_id, "eval")
    tq.save_eval(rows, str(out_dir), {
        "adapter": Path(adapter_dir).name, "csv": Path(csv_path).name, "csv_md5": md5_before,
        "model": "A.X-4.0-Light 4bit NF4 + LoRA", "fine_tuned": True, "gen_sec": seconds,
        "csv_md5_unchanged": file_md5(csv_path) == md5_before,
    })
    report = build_report(rows, base.label, exclude)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path")
    parser.add_argument("out_dir")
    parser.add_argument("--adapter", default=str(DEFAULT_ADAPTER))
    parser.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE))
    args = parser.parse_args()
    try:
        run_eval(args.csv_path, args.out_dir, args.adapter, tuple(args.exclude))
    except FileExistsError as error:
        sys.exit(str(error))
