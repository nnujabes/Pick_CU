# Hugging Face 모델

팀 모델 파일은 용량 때문에 git에 없고, Hugging Face에 공개로 올려 두었습니다. 로그인 없이 받을 수 있습니다.

| 모델 | 링크 | 크기 |
| --- | --- | --- |
| 하영 LoRA 어댑터 (4bit + 어댑터용) | https://huggingface.co/nnujabes/pickcu-ax-4.0-light-lora | 약 162MB |
| A.X 양자화 GGUF Q5_K_M (web3 최종 모델, Ollama용) | https://huggingface.co/nnujabes/pickcu-ax-4.0-light-gguf | 약 5.2GB |

학습 설정, 평가 결과, 사용법은 각 링크의 모델 카드에 있습니다.

## 받기

```bash
pip install -U huggingface_hub

# 어댑터: README.md는 받지 않도록 파일 두 개만 지정
hf download nnujabes/pickcu-ax-4.0-light-lora adapter_model.safetensors adapter_config.json \
  --local-dir members/hayoung/finetune_v1/adapter/best

# GGUF: 받은 뒤 Ollama에 등록
cd members/hyeokjun/curator_web3/model/ax-4.0-light
hf download nnujabes/pickcu-ax-4.0-light-gguf pickcu-ax-Q5_K_M.gguf --local-dir .
sha256sum -c SHA256SUMS
ollama create pickcu-ax:q5_k_m -f Modelfile
```

| 파일 | sha256 |
| --- | --- |
| `adapter_model.safetensors` | `f95d9f5e429f0f16c854c769253ee0dd4df075f91b5ea3cc29fd56b7b157cc8b` |
| `pickcu-ax-Q5_K_M.gguf` | `324e1bcb590b67df7928d72c2d13d55ecf70ef30e766bd0c48608d342fa71a6f` |
