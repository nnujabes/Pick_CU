# Pick CU 웹 3 (최종 실행본)

팀 코드를 이 폴더에 모아 양자화한 A.X 4.0 Light(GGUF Q5_K_M)로 실행하는 최종본입니다. 다른 멤버의 폴더는 수정하지 않았으며, 명령 하나로 화면, API, 모델 호출이 함께 켜집니다.

## 실행

Node.js, Python, Ollama가 필요합니다. WSL에서는 FastAPI가 설치된 환경을 먼저 켭니다.

```bash
cd members/hyeokjun/curator_web3
pip install -r server/requirements.txt   # 처음 한 번
npm install                              # 처음 한 번
npm start
```

브라우저에서 http://localhost:5175 를 엽니다. 다른 화면의 `npm start`가 켜져 있으면 API 포트(8000)가 겹치므로 먼저 끕니다.

## 모델 파일이 없어도 됩니다

GGUF 파일은 약 5.2GB라 git에 없습니다. 팀원은 모델을 받지 않아도 같은 명령으로 실행할 수 있습니다.

| PC 상태 | 문장 해석 |
| --- | --- |
| Ollama에 `pickcu-ax:q5_k_m` 등록됨 | 양자화 A.X |
| Ollama나 모델이 없음 | 규칙 파서 (`server/nlu.py`). 오류 없이 화면과 추천이 동작 |

모델 등록 방법은 `model/ax-4.0-light/README.md`에 있습니다.

## 구성

| 경로 | 내용 | 원본 |
| --- | --- | --- |
| `src/` | 화면 | `members/hyeokjun/curator_web2` |
| `server/main.py`, `service.py`, `nlu.py`, `review_store.py` | API | `members/jongho/fastapi` (경로만 수정) |
| `server/query_parser.py` | 문장 해석. 모델 호출만 Ollama로 변경 | `members/hayoung/finetune_v1/code/query_parser.py` |
| `model/` | 양자화 재현 코드와 평가 결과 (`model/README.md`) | 혁준 |

필터 엔진과 상품 DB는 저장소 공용 폴더 `backend/`를 읽기만 합니다. `server/`는 복사본이라, 원본이 바뀌면 필요한 부분을 다시 반영해야 합니다.
