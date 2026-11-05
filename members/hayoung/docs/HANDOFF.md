# 인수인계: 편의점 큐레이터 LLM 작업 (로컬 PC 세션 → 166번 서버 세션)

- 작성: 2026-11-04. 로컬 Windows PC의 Claude Code 세션(`pickcu-86`)이 작성했어요.
- 받는 쪽: 166번 서버(`workstation6`)에서 `/home/dgu`로 실행 중인 Claude Code 세션 `06cc65ac-22cf-4528-bf7d-e5c2941beeec`
- 이유: 로컬 PC와 서버 사이 wifi가 불안정해요. 그래서 **4090이 필요한 작업은 앞으로 모두 서버의 이 세션이 직접 맡아요.** SSH를 거치지 않아요.

---

## 0. 반드시 지킬 규칙 (사용자가 직접 지시함)

1. **답변은 항상 한국어로** 해요. 코드, 명령어, 경로, 고유명사는 원문 그대로 둬요.
2. **사용자가 "멈춰" 또는 "잠깐 멈춰봐"라고 하면 즉시 멈춰요.** 그리고 한 일과 안 한 일을 정확히 보고해요.
3. **학습(파인튜닝)은 사용자가 명시적으로 지시할 때까지 하지 마세요.** 아직 지시가 없었어요.
4. **입력 데이터 파일은 수정하지 마세요.** 대상은 `train/eval/sheet4`, `dev*.csv`, `train*.csv`이고, 결과는 항상 새 파일로 저장해요.
5. **test 파일은 사용자가 허락할 때까지 절대 열거나 사용하지 마세요.** 지금 서버에는 올리지도 않았어요.
6. **평가할 때 정답 누출을 금지해요.**
   - 모델 프롬프트에는 `입력 문장` 텍스트만 넣어요. 성분, 방향, 카테고리, 상황ID, 말투 유형, 작성자는 절대 넣지 마세요.
   - 정답 칸은 채점에만 써요.
   - 예측은 반드시 A.X 모델이 해야 해요. Claude가 직접 맞히면 안 돼요.
7. **평가 전에 0단계 데이터 점검을 먼저 하고 보고해요.** 고유값, 빈 칸, 중복, 개수, train과 dev의 겹침을 확인해요. 애매한 라벨이나 사용자 설명과 다른 점(행 수, 열 이름 등)은 임의로 처리하지 말고 먼저 물어보세요.
8. **실행 중이라고 보고하기 전에 실제로 확인해요.** 프로세스, tmux, 로그를 보고, 파일을 올렸으면 크기와 md5도 확인해요. 실수했으면 솔직히 인정해요. (11/3에 0바이트 업로드를 "실행 중"이라고 잘못 보고한 적이 있어요.)
9. **긴 작업은 tmux로 돌려요.** nohup은 쓰지 마세요. 내가 띄운 백그라운드 프로세스는 끝나면 정리해요.
10. **사용자 동의 없이 파일을 삭제하지 마세요.**
11. **`dgu` 계정은 여러 사람이 같이 써요.**
    - 다른 사람의 폴더, conda env, tmux 세션, GPU 프로세스는 절대 건드리지 마세요. 예: sweepick-*, alpenact_*, isaacsim, DAPIER, perpet, envs `isaac`/`molmoact`, tmux `isaac`
    - 무거운 작업 전에는 `nvidia-smi`로 GPU가 비어 있는지 확인해요.
    - `~/llm_project_knlee/`는 팀원(이규남) 폴더라서 수정하지 마세요.
12. **서버 비밀번호는 어디에도 저장하지 마세요.**
13. **커밋과 푸시는 사용자가 요청할 때만** 해요.

## 1. 사용자와 프로젝트

- **사용자:** 박하영 (hayoung, git `hayoung-create`). 아이넷팀(다이브 1기 NLP/LLM 과정)에서 **LLM 담당**이에요.
- **팀원:** 조혁준(팀장), 이규남(knlee, PR 리뷰어), 김종호
- **프로젝트:** "편의점 큐레이터"
  - 사용자의 자연어 요청을 분석해서 CU 상품 중 영양 조건에 맞는 것을 추천해요.
  - LLM 부분은 문장 하나를 보고 **카테고리 1~3개, 핵심 영양 성분 1개, 방향(높음/낮음)**을 뽑아요.
  - 이 결과로 DB를 필터링해서 상품을 추천해요.
  - 문서는 `docs/project-details/` (Notion 내보내기)에 있어요. 최신 기획은 `02_요구사항-분석-및-기획/07_기획보고서-최종-C-(Vision-LLM-반영-최신).md`예요.
- **모델:** `skt/A.X-4.0-Light`
  - Qwen2 계열, 약 7B, 어휘 102,400개
  - 공식 채팅 템플릿을 그대로 써요. 형식은 `<|im_start|><|system|>…<|im_end|><|im_start|><|user|>…<|im_end|><|im_start|><|assistant|>`이고, eos는 `<|im_end|>`(27)예요.
- **식약처 원본 데이터:** 쓰지 않기로 결정했어요.
- **팀 저장소:** `github.com/nnujabes/Pick_CU`
  - 사용자는 `members/hayoung/` 폴더 안에서만 작업해요.
  - 브랜치는 `hayoung/<작업>`, 커밋 메시지는 `[hayoung] ...` 형식이에요.
  - main에 직접 푸시하거나 force push하면 안 돼요.
  - 팀 규칙은 `docs/Pick_CU_team_CLAUDE.md`에 있어요.

## 2. 서버 환경 (166번 = "연산서버" = workstation6)

- Ubuntu 24.04, RTX 4090 24GB, 디스크 여유 약 699GB
- sudo, nvcc, Ollama는 없어요.
- **conda env `llm-torch`** (`~/miniconda3/envs/llm-torch`)
  - Python 3.10, torch 2.6.0+cu124, transformers 5.20.2, accelerate 1.15.0, bitsandbytes 0.50.2
  - **`peft`, `trl`, `datasets`는 없어서 지금은 추론만 가능해요.**
  - 파인튜닝할 때는 기존 env에 설치하지 말고, `llm-torch`를 복제한 별도 학습 env를 만드는 걸 권장해요 (다른 사람도 이 env를 쓸 수 있어서요). 설치 위치는 사용자에게 먼저 확인하세요.
  - transformers 5.20과 호환되는 peft/trl 버전도 확인이 필요해요.
- **A.X 원본 가중치:** `~/.cache/huggingface/hub/models--skt--A.X-4.0-Light/` (rev `ba21c20e…`, bf16 14.5GB)
  - bf16으로 올리면 GPU 메모리 약 13.5GiB를 써요.
  - 예상: QLoRA는 여유 있고, bf16 LoRA는 빠듯해요.
- **GGUF:** 서버에는 없어요. 로컬 4060 실험에서 `mykor/A.X-4.0-Light-gguf`의 `A.X-4.0-Light-Q4_K_M.gguf`(sha256 `6bd9cb8ccaae2efc5c33c7b5e443c2f820d4731130df38cd24f7ba494146ead5`)를 썼어요. 필요하면 서버에서 HF로 직접 받으면 돼요.

## 3. 폴더 구조 (`~/LLM_CU_project_daiyoung/`)

| 경로 | 내용 |
| --- | --- |
| `HANDOFF.md` | 이 문서 |
| `data/` | **최신 입력 데이터 (수정 금지)**: `dev.csv`, `train.csv`, `dev_category.csv`, `train_category.csv` (md5는 아래 참고) |
| `baseline/` | 11/3 베이스라인 A, B (`eval.jsonl` 40문장, 4090 bf16): 스크립트와 결과 |
| `dev_baseline/` | 11/4 dev 216문장 성분+방향 베이스라인 (4090 bf16): 스크립트와 결과 |
| `wsl_LLM_CU_project/` | 로컬 WSL 작업 폴더 스냅샷. 크롤러, 파서, 추천 에이전트, Streamlit/Chainlit 앱, `train.jsonl`/`eval.jsonl`/`sheet4.csv`/`convert.py`, 로컬 4060 GGUF 결과 (`dev_category_gguf/` = 유효, `dev_category_gguf_old/` = **취소된 결과, 무시**) |
| `docs/project-details/` | Notion 내보내기 문서 26개와 README |
| `docs/Pick_CU_team_CLAUDE.md` | 팀 저장소 규칙 |
| `llm-project/` | 팀원 `cu_data.zip`의 압축 해제본 (VLM 영양 파서, 크롤러, 라벨 이미지 3,873장) |
| `cu_data.zip` | 위 zip의 복사본. 원본은 `~/llm_project_knlee/`에 있고 건드리지 않아요 |

**입력 파일 md5**

| 파일 | md5 |
| --- | --- |
| `dev.csv` | `aa00d1532dc91728b896015ca81f01ba` |
| `train.csv` | `3d55ee42988642ae6363f0e55aca9fef` |
| `dev_category.csv` | `103403c86413b2082bff0ded274d38b6` |
| `train_category.csv` | `3e337971d3ab0fd5d131d0af8b20958c` |
| `eval.jsonl` | `7fd2ba0ce404add3dfa3a96903cf6433` |
| `train.jsonl` | `8f797c3e9a7519969422592debdda623` |

## 4. 데이터 사실 (0단계 점검 결과)

**공통 형식**
- 열: `상황ID, 입력 문장, 말투 유형, 작성자, 성분, 방향`. `*_category.csv`에는 `카테고리1, 카테고리2, 카테고리3`이 더 있어요.
- 라벨 매핑: 열량→calories, 단백질→protein, 나트륨→sodium, 탄수화물→carbs, 당류→sugar, 지방→fat, 높음→high, 낮음→low. 표기 오류는 없어요.

**dev** (216행, 헤더 포함 217줄)
- 상황 12개: S016, S017, S034, S035는 각 20문장 (작성자 AI(Claude)), S2008~S2072의 8개는 각 17문장 (작성자 종호)
- train과 겹치는 상황ID나 문장은 없어요.
- 작성자는 2명뿐이에요. 사용자는 "팀원 3명분"이라고 했는데, 확인이 필요해요.

**train** (2,700행)
- 902번째 줄에 완전히 빈 행이 하나 있어요. 제외해요.
- 상황 90개, 각 30문장
- **"나트륨 높음"과 "단백질 낮음" 라벨이 하나도 없어요.** dev에는 나트륨 높음이 20문장 있어요. 파인튜닝 전에 사용자에게 꼭 짚어야 해요.

**카테고리 칸의 의미 (중요)**
- 문장에 카테고리가 언급됐는지가 아니에요. **그 요청에 어울리는 상품 카테고리 후보 1~3개**예요.
- 값은 간편식사, 식품, 과자류, 음료, 아이스크림 5가지예요.
- **순서는 신뢰할 수 없어서 순서 없는 집합으로 비교해요.**
- null은 정답으로 쓰이지 않아서, 모델은 항상 1개 이상 답해야 해요.
- dev 정답 개수 분포: 1개 31, 2개 49, 3개 136

## 5. 지금까지의 베이스라인 (모두 파인튜닝 전)

| 실험 | 환경 | 데이터 | 결과 |
| --- | --- | --- | --- |
| A | 4090 bf16 | `eval.jsonl` 40 | 형식 정의 없음. 엄격 채점 0% (키 이름이 제각각), 의미 채점 82.5% |
| B | 4090 bf16 | `eval.jsonl` 40 | 출력 형식 명시 + few-shot 9개: 성분+방향 92.5% (37/40) |
| dev | 4090 bf16 | `dev.csv` 216 | 형식 명시 + few-shot 9개: **성분+방향 179/216 = 82.9%**. 나트륨 20/40으로 가장 약함 |
| dev_category v2 | 로컬 4060, GGUF Q4_K_M | `dev_category.csv` 216 | few-shot 12개: **성분+방향 81.5%, 카테고리 완전 일치 26.9%, 포함률 0.671, 1순위 일치 95.8%, 전체 (a) 25.5% / (b) 25.9%** |

**dev_category v2 상세**
- 모델은 카테고리를 평균 1.68개만 골라요 (3개는 0번). 정답은 평균 2.49개예요.
- 가장 자주 빠뜨리는 카테고리는 음료(70)와 과자류(55)예요.
- 공통 약점:
  - S034(회식 다음 날 → sodium/low)를 calories로 답함
  - S035(땀 흘린 뒤 → sodium/high)를 low로 답함
  - S2045(수유 → calories/high)를 protein으로 답함
  - AI(Claude)가 쓴 상황은 카테고리 완전 일치 0/80
- 결과 위치: `wsl_LLM_CU_project/dev_category_gguf/`
  - `summary.json`, `rows.csv`, `wrong_*.csv`, `prompt.txt`, `fewshot.json`, `model_info.json`
  - 스크립트 `dev_category_gguf.py`는 llama-cpp-python 기반이에요. 4090에서 HF transformers로 재현하려면 `dev_baseline/dev_baseline.py`의 로딩·생성 방식과 합쳐서 쓰면 돼요.
- `dev_category_gguf_old/`는 잘못된 지시문("카테고리는 언급될 때만, 없으면 null")으로 돌린 결과예요. **사용자가 취소했으니 무시하세요.**

**평가 스크립트 공통 사항**
- greedy (`do_sample=False` / temperature 0)
- 코드블록을 제거한 뒤 JSON을 파싱하고, 실패하면 `{...}` 부분을 추출해요. 그래도 안 되면 파싱 실패로 세요.
- grammar 같은 강제 디코딩은 쓰지 않아요.
- few-shot은 train에서 seed 42로 뽑아요. 성분과 방향이 골고루 들어가게 하고, dev 문장이나 상황ID와 겹치지 않게 하고, dev 문장과 difflib 유사도가 0.8 이상인 문장은 제외해요.

## 6. 남은 일 / 다음 단계 후보

1. **파인튜닝 준비** (사용자 지시 후에만)
   - 학습 env 위치를 정해요.
   - peft, trl, datasets를 호환 버전으로 설치해요.
   - QLoRA 또는 LoRA로 메모리를 측정해요.
   - `train_category.csv` → chat 형식 변환은 `wsl_LLM_CU_project/convert.py`를 참고해요.
   - 목표: 위 dev 베이스라인을 넘는 거예요.
2. **train 라벨 공백 보고:** 나트륨 높음과 단백질 낮음 문장이 없어요.
3. **팀 확인이 필요한 라벨:** "담백한" → fat/low, "수유 중 든든히" → calories/high. 그리고 dev에 세 번째 팀원 데이터가 빠졌는지 확인해야 해요.
4. **Pick_CU 저장소로 코드를 옮길 때:** 먼저 `hayoung/...` 브랜치를 만들어요.
5. **앱 연결:** 앱 코드(`test_app.py`, `test_chainlit.py`)는 아직 Ollama `llama3.2:3b`와 `exaone3.5`를 써요. A.X로 바꾸는 작업이 남아 있어요.

## 7. 로컬 PC 쪽 (참고만, 서버에서는 접근할 수 없어요)

- Windows `C:\Users\user\Documents\PickCU` (Notion 문서, Pick_CU 저장소)
- WSL `/home/ai/Daive-LLM/LLM_CU_project` (위 스냅샷의 원본)
- 로컬 GPU는 RTX 4060 8GB예요. GGUF용 conda env `axgguf`와 `~/models/ax-gguf/`가 있어요.

## 추가 데이터 (2026-11-04)
- `data/dev_2nut.csv` (216행, md5 7a983f96…), `data/train_2nut.csv` (2,700행, md5 7afc520e…)
- 컬럼: 상황ID, 입력 문장, 말투 유형, 작성자, 성분1, 방향1, 성분2, 방향2
- 용도: 카테고리는 하지 않기로 함. 문장을 보고 성분 2개(+방향)를 뽑는 A.X 정확도 측정용. 수정 금지, 정답 누출 금지 규칙 동일.
- 지시서: `docs/NutriCU_2nut_baseline.pdf` (사용자가 보낸 2성분 베이스라인 문서, 2026-11-04 업로드)
- `data/dev_pair.csv` (216행, md5 34987606…), `data/train_pair.csv` (2,700행, md5 397e7431…) 추가 (2026-11-04). 컬럼은 *_2nut.csv와 같지만 성분2/방향2 값이 다름 (예: S016 2nut=열량/높음, pair=지방/낮음). 어느 파일을 쓸지는 사용자 지시를 따를 것.
- `data/dev_pair_v2.csv` (216행, md5 f69ebeac…), `data/train_pair_v2.csv` (2,820행, md5 0d2c8a43…) 추가 (2026-11-04). 컬럼은 *_pair.csv와 같음. train이 120행 늘어남. 가장 최신 버전이지만, 어느 파일을 쓸지는 사용자 지시를 따를 것.
