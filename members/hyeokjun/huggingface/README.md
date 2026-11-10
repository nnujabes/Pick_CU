# Hugging Face에 올린 모델

팀 모델 파일은 용량 때문에 git에 없어서 Hugging Face 비공개 저장소 두 곳에 올렸습니다. 둘 다 혁준(nnujabes) 계정입니다.

| 저장소 | 내용 | 크기 | 쓰는 곳 |
| --- | --- | --- | --- |
| [`nnujabes/pickcu-ax-4.0-light-lora`](https://huggingface.co/nnujabes/pickcu-ax-4.0-light-lora) | 하영이 학습한 LoRA 어댑터 (`adapter_model.safetensors`, `adapter_config.json`) | 약 162MB | `members/hayoung/finetune_v1` (4bit + 어댑터, transformers) |
| [`nnujabes/pickcu-ax-4.0-light-gguf`](https://huggingface.co/nnujabes/pickcu-ax-4.0-light-gguf) | 어댑터를 합쳐 Q5_K_M으로 양자화한 GGUF와 `Modelfile` | 약 5.2GB | `members/hyeokjun/curator_web3` (Ollama, 최종 모델) |

각 저장소의 설명(모델 카드)에 학습 설정, 평가 결과, 사용법을 적었습니다.

## 받기 전에

비공개 저장소라 접근 권한이 있는 Hugging Face 토큰이 필요합니다. 권한이 없으면 혁준에게 요청합니다.

```bash
pip install -U huggingface_hub
hf auth login
```

## 어댑터 받기 (4bit + 어댑터로 실행할 때)

```bash
hf download nnujabes/pickcu-ax-4.0-light-lora adapter_model.safetensors adapter_config.json \
  --local-dir members/hayoung/finetune_v1/adapter/best
sha256sum members/hayoung/finetune_v1/adapter/best/adapter_model.safetensors
# f95d9f5e429f0f16c854c769253ee0dd4df075f91b5ea3cc29fd56b7b157cc8b
```

- 파일 두 개만 지정해서 받습니다. 저장소의 `README.md`까지 받으면 하영 폴더의 기존 `README.md`를 덮어씁니다.
- 다른 위치에 받았다면 `QUERY_PARSER_ADAPTER` 환경변수로 경로를 알려 줍니다(`members/hayoung/finetune_v1/README.md` 참고).
- 원본 모델 `skt/A.X-4.0-Light`(약 15GB)는 처음 실행할 때 자동으로 받습니다.

## GGUF 받기 (web3를 양자화 A.X로 실행할 때)

```bash
cd members/hyeokjun/curator_web3/model/ax-4.0-light
hf download nnujabes/pickcu-ax-4.0-light-gguf pickcu-ax-Q5_K_M.gguf --local-dir .
sha256sum -c SHA256SUMS
ollama create pickcu-ax:q5_k_m -f Modelfile
```

이후 실행 방법은 `members/hyeokjun/curator_web3/model/README_MODEL_SHARE.md`와 같습니다. 모델을 받지 않아도 web3는 규칙 파서로 동작합니다.

## 해시

| 파일 | sha256 |
| --- | --- |
| `adapter_model.safetensors` | `f95d9f5e429f0f16c854c769253ee0dd4df075f91b5ea3cc29fd56b7b157cc8b` |
| `pickcu-ax-Q5_K_M.gguf` | `324e1bcb590b67df7928d72c2d13d55ecf70ef30e766bd0c48608d342fa71a6f` |

## 올리지 않은 것

- 학습·dev·test 데이터와 시스템 프롬프트 원문은 올리지 않았습니다. 프롬프트는 이 저장소의 `members/hayoung/finetune_v1/code/query_parser.py`에 있습니다.
- 원본 모델은 `skt/A.X-4.0-Light`(Apache 2.0)를 그대로 쓰므로 올리지 않았습니다.
