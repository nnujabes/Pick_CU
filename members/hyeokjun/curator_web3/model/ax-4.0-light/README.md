# A.X 파인튜닝 모델 GGUF (Q5_K_M)

하영의 파인튜닝 어댑터(`members/hayoung/finetune_v1/adapter/best`)를 원본 `skt/A.X-4.0-Light`에 합쳐(merge) GGUF로 바꾸고 Q5_K_M으로 양자화한 모델입니다. Ollama로 실행하며, 원본 모델(14GB)과 어댑터 없이 이 파일 하나로 돌아갑니다.

| 항목 | 값 |
| --- | --- |
| 원본 모델 | `skt/A.X-4.0-Light` (revision `ba21c20ea1b31ded1ec3e2fb432335077dc4be98`) |
| 어댑터 | `members/hayoung/finetune_v1/adapter/best` (LoRA r16, alpha 32, sha256 `f95d9f5e…cc8b`) |
| 파일 | `pickcu-ax-Q5_K_M.gguf`, 약 5.2GB (5,175,334,784바이트) |
| sha256 | `324e1bcb590b67df7928d72c2d13d55ecf70ef30e766bd0c48608d342fa71a6f` (`SHA256SUMS`) |
| Ollama 이름 | `pickcu-ax:q5_k_m` |
| 만든 날 | 2026-11-06, 혁준 PC WSL (RTX 4060 Laptop 8GB, 메모리 15GB) |

**모델 파일은 git에 없습니다.** 약 5.2GB라 GitHub에 올릴 수 없고, 저장소 `.gitignore`가 `*.gguf`를 제외합니다. 팀원은 받지 않아도 됩니다(`../README.md` 참고).

## 등록 (모델 파일이 있는 PC만)

1. 모델 파일을 이 폴더의 `Modelfile`과 같은 폴더에 둡니다. `Modelfile`이 `./pickcu-ax-Q5_K_M.gguf`를 가리킵니다.
2. 파일이 맞는지 확인하고 Ollama에 등록합니다.

```bash
sha256sum -c SHA256SUMS
ollama create pickcu-ax:q5_k_m -f Modelfile
ollama run pickcu-ax:q5_k_m "5천원 이하로 운동 후에 먹을 거"
# {"nutrients": [{"nutrient": "protein", "direction": "high"}, {"nutrient": "fat", "direction": "low"}]}
```

## dev 결과

dev 216문장(`members/hayoung/dev_pair_v3_baseline/dev_pair_v3.csv`), 두 쌍을 모두 맞혀야 정답(순서 무관)입니다. 비교 기준은 4bit NF4 + 어댑터(transformers) 결과인 `members/jongho/eval/results/dev_4060`입니다.

| 시스템 프롬프트 | 정답 | 기준과 문장별 예측 일치 | 형식 오류 | 문장당 시간 | 결과 폴더 |
| --- | --- | --- | --- | --- | --- |
| 학습 프롬프트 (sha `06818f0f…`) | **186/216 (86.1%)**, 기준과 같음 | 213/216 | 0 | 0.81초 | `results/dev_prompt06818f0f/` |
| PR #28 프롬프트 (sha `836df788…`) | **184/216 (85.2%)** | 209/216 | 1 | 0.81초 | `results/dev_prompt836df788/` |

- 학습 프롬프트에서 기준과 예측이 다른 3문장 중 GGUF만 맞힌 것 1개, 기준만 맞힌 것 1개, 둘 다 틀린 것 1개입니다.
- PR #28 프롬프트의 기준 비교는 학습 프롬프트로 잰 `dev_4060`(186)과 한 것입니다. 하영이 같은 PR #28 프롬프트로 4bit + 어댑터를 잰 결과는 185/216이라, GGUF가 1문장 적습니다. 기준과 다른 7문장 중 GGUF만 맞힌 것 2개, 기준만 맞힌 것 4개입니다.
- 형식 오류 1개는 "애들 간식 머사줌 키크는거로"에 허용되지 않은 성분 `calcium`을 낸 경우입니다. `parse_query`에서는 `None`(`invalid_output`)이 됩니다.
- test 240문장 결과는 `../test_compare/`에 있습니다. 학습 프롬프트 210/240(87.5%), PR #28 프롬프트 207/240(86.3%)입니다.
- 이 평가는 `parse_query`를 거치지 않고 모델만 부릅니다. 그래서 PR #28의 인삿말 거르기(`is_no_condition`)는 결과에 들어가지 않습니다.

## 웹에서 쓰기

`curator_web3`에서 `npm start`를 실행합니다. `../../server/query_parser.py`가 Ollama로 이 모델을 호출합니다.

- 시스템 프롬프트는 요청마다 `query_parser.SYSTEM_PROMPT`를 넘깁니다. 프롬프트가 바뀌어도 `Modelfile`을 다시 등록할 필요가 없습니다.
- GPU 8GB에서는 원본 + 어댑터 서버와 Ollama 모델을 동시에 올릴 수 없습니다. 하나만 켭니다.

## 만드는 법

모두 CPU로 하며 GPU는 쓰지 않습니다. 혁준 PC 기준 전체 약 3분입니다.

| 단계 | 명령 | 시간 | 최대 메모리 |
| --- | --- | --- | --- |
| 1. merge | `python merge_lora.py` | 47초 | 약 10GB |
| 2. GGUF 변환 | `python llama.cpp/convert_hf_to_gguf.py merged --outtype bf16 --outfile pickcu-ax-bf16.gguf` | 48초 | 약 3.7GB |
| 3. 양자화 | `llama.cpp/build/bin/llama-quantize pickcu-ax-bf16.gguf pickcu-ax-Q5_K_M.gguf Q5_K_M 8` | 1분 | 약 2.5GB |
| 4. 등록 | `ollama create pickcu-ax:q5_k_m -f Modelfile` | 수 초 | |

- **merge (`merge_lora.py`):** 원본 조각을 텐서 단위로 읽어 `W + (alpha / r) × (B @ A)`를 더하고, 약 2GB씩 나눠 저장합니다. PEFT LoRA와 같은 식입니다. 원본을 한 번에 메모리에 올리지 않아 WSL 기본 메모리(약 15GB)로 됩니다. 스크립트 안의 경로(`BASE`, `ADAPTER`, `OUT`)를 자기 환경에 맞춥니다.
- **llama.cpp:** `llama_cpp_commit.txt`의 커밋을 CPU로 빌드했습니다(`llama-quantize`만 빌드).
- **토크나이저 등록 (`llama_cpp_tokenizer.patch`):** A.X 토크나이저는 llama.cpp 변환기 목록에 없어 변환이 멈춥니다. A.X는 별도 규칙 없이 ByteLevel 기본 정규식을 쓰므로 GPT-2와 같은 방식입니다. 그래서 A.X 토크나이저 해시(`261dca7f…4ff9`)를 `gpt-2`로 등록하는 세 줄을 로컬에만 추가했습니다. 공개된 A.X GGUF(`mykor/A.X-4.0-Light-gguf`)도 `gpt-2`로 되어 있습니다.
- **Modelfile:** 학습 때와 같은 대화 형식 `<|im_start|><|system|>…<|im_end|><|im_start|><|user|>…<|im_end|><|im_start|><|assistant|>`를 직접 적었습니다. GGUF에 들어 있는 원본 템플릿(jinja)을 Ollama가 버전마다 다르게 해석할 수 있기 때문입니다. 생성은 `temperature 0`, `num_predict 128`, stop `<|im_end|>`·`<|im_start|>`이고, `SYSTEM`은 PR #28 프롬프트(sha `836df788…`)입니다.

## 주의할 점

- 하영은 4bit로 줄인 원본 위에서 어댑터를 학습했습니다(QLoRA). 여기서는 bf16 원본에 합친 뒤 Q5_K_M으로 줄였으므로 학습 조건과 조금 다릅니다. dev 결과가 기준과 같아서 차이는 작다고 봅니다.
- 어댑터가 바뀌면 merge부터 다시 해야 합니다. 시스템 프롬프트만 바뀌면 다시 만들 필요가 없습니다(`Modelfile`의 `SYSTEM`만 고쳐 다시 등록하거나, `../../server/query_parser.py`처럼 요청마다 넘깁니다).

## 파일

| 파일 | 내용 |
| --- | --- |
| `Modelfile` | Ollama 등록 설정 |
| `SHA256SUMS` | GGUF 해시 |
| `merge_lora.py` | 층별 merge |
| `eval_gguf.py` | Ollama로 dev 평가, 기준과 문장별 비교 |
| `llama_cpp_commit.txt`, `llama_cpp_tokenizer.patch` | 쓴 llama.cpp 커밋과 토크나이저 등록 패치 |
| `results/` | dev 평가 결과 (`summary.json`, 문장별 `rows.json`) |
