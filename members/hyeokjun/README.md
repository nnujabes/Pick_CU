# hyeokjun

## 담당 역할

LLM 담당입니다. A.X 4.0 Light의 조건 추출 성능을 평가하고 파인튜닝 계획을 세웠으며, 실제 상품 DB와 추천 엔진을 연결한 웹 화면을 만들었습니다.

## 이 폴더가 하는 일

| 위치 | 내용 | 상태 |
| --- | --- | --- |
| `curator_web/` | Pick CU 웹 프론트, API 형식(`api_contract.json`) | 브랜치 `hyeokjun/web-demo`에 push함. PR 전 |
| `slot_eval/` | A.X 4.0 Light 기준선 테스트, 파인튜닝 샘플 데이터 | **저장소에 없음.** WSL `~/Daive-LLM/pickcu/members/hyeokjun/slot_eval/`에만 있고 커밋하지 않음 |

화면이 호출하는 API 서버는 `members/jongho/fastapi/`로 옮겼습니다. 이 코드는 아직 커밋되지 않아서 `hyeokjun/web-demo`만 받으면 화면에 API 연결 오류가 나옵니다.

## 지금까지 한 작업

### 1. A.X 4.0 Light 기준선 테스트 (2026-11-04)

Ollama의 `hf.co/mykor/A.X-4.0-Light-gguf:Q5_K_M`으로 문장을 조건 JSON으로 바꾸는 성능을 쟀습니다. 일반 조건 90문장, 다중 영양소 75문장, 전문용어 10문장을 썼습니다.

JSON 스키마를 강제한 결과입니다. strict는 영양소 6개 전부 일치, lenient는 정답 영양소만 확인한 값입니다.

| 유형 | strict | lenient |
| --- | --- | --- |
| 영양소 2개 직접 말함 | 100% | 100% |
| 영양소 3개 직접 말함 | 100% | 100% |
| 영양소 4개 이상 직접 말함 | 93% | 100% |
| 상황 표현 | 13% | 80% |
| 제외 표현("상관없어") | 53% | 53% |
| 전문용어 | 40% | 80% |

- 직접 말한 영양소는 잘 이해합니다.
- 상황 표현에서는 말하지 않은 영양소까지 채우고, 제외 표현은 선호로 오해합니다.
- 린매스업·커팅 같은 일부 전문용어는 빈 출력이 나옵니다.

### 2. 파인튜닝 계획 (2026-11-04)

- 출력은 JSON 스키마 강제 방식으로 합니다.
- 프롬프트 v1 실험은 생략하고, 숫자 지어내기와 재질의 누락은 코드 후처리와 프롬프트 규칙으로 해결합니다.
- 운동 후 라벨은 단백질↑ 지방↓ 당↓입니다.
- QLoRA(r16, alpha32, lr 2e-4, 2~3 epoch)를 RTX 4090에서 돌리고, merge → GGUF → Q5_K_M → Ollama 순서로 변환합니다.
- 데이터는 2,000~3,500행으로 만듭니다. 팀원의 2,500문장과 상황표 200개를 다중 영양소로 재라벨링하고, 제외 표현 300~500행과 전문용어 행을 더합니다.
- 전문용어 테스트셋은 평가 전용이라 학습에 넣지 않습니다.

100행 샘플(`slot_eval/finetune/ft_data_v0.xlsx`)까지 만들었고, 파인튜닝은 아직 돌리지 않았습니다.

### 3. Pick CU 웹 화면 (2026-11-05)

- **실제 데이터 연결:** 상품 2,154개와 팀 필터 엔진 결과를 그대로 씁니다. 팀 코드와 DB는 읽기만 합니다.
- **첫 화면:** 왼쪽에 카테고리 칩(1~3개)과 대화, 입력창이 있고 오른쪽에 3D 편의점이 있습니다.
- **추천 결과:** 추천이 나오면 3D 모형 자리에 같은 크기의 카드 5개가 세로 한 줄로 나옵니다. [편의점 보기]로 모형을 다시 열 수 있습니다.
- **3D 편의점:** 진열대 6개에 마우스를 올리면 빛나고 말풍선이 뜨며, 클릭하면 정면으로 돌아가 상품 패널이 열립니다.
- **패널:** 전체 상품(탭, 검색, 정렬, 행사 필터, 20개씩 불러오기), 장바구니(새로고침해도 유지), 내 리뷰가 있습니다.
- **상품 사진:** DB의 외부 이미지 주소를 쓰고, 실패하면 카테고리 대체 이미지를 보여 줍니다.
- **리뷰:** 별점과 한 줄 리뷰를 저장하고 추천 점수에 반영합니다. 같은 브라우저에서 같은 조합을 다시 쓰면 수정됩니다.

자세한 내용은 `curator_web/README.md`에 있습니다.

## 실행 방법

저장소 루트에서 처음 한 번 설치합니다. API 서버 코드(`members/jongho/fastapi/`)가 함께 있어야 합니다.

```bash
pip install -r members/jongho/fastapi/requirements.txt
cd members/hyeokjun/curator_web/frontend
npm install
```

화면과 API 서버를 함께 켭니다. 화면은 http://localhost:5173 입니다.

```bash
cd members/hyeokjun/curator_web/frontend
npm start
```

## 핵심 함수

프론트의 주요 컴포넌트와, 다른 팀원이 바꾸게 될 연결 지점입니다. API 형식 전체는 `curator_web/api_contract.json`에 있습니다.

| 이름 | 입력 | 출력 | 예시 |
| --- | --- | --- | --- |
| `postRecommend` (`frontend/src/api/client.ts`) | 문장, 카테고리 1~3개, 직전 문장 | 해석한 조건, 추천 5개 | `postRecommend({ text, categories, pending_text: null })` |
| `fetchProducts` (같은 파일) | 카테고리, 검색어, 정렬, 행사, 페이지 | 상품 목록, 전체 개수 | `fetchProducts({ category: "음료", q: "", sort: "price", promo: "", page: 1 })` |
| `postReview` (같은 파일) | 바코드, 별점, 한 줄 리뷰, 세션 ID 등 | 리뷰 ID, 상품별 별점 | `postReview({ barcodes, rating: 5, ... })` |
| `splitBrand` (`frontend/src/utils/nutrition.ts`) | 상품명 | 브랜드, 이름 | `splitBrand("득템)뉴닭가슴살훈제")` |
| `parse_request` (`members/jongho/fastapi/nlu.py`) | 문장, 카테고리 | A.X 스키마 형식의 조건 | A.X를 연결할 때 이 함수만 교체 |

## 필요한 라이브러리

Python 3.12.10, Node.js 24.18.0에서 사용한 버전입니다.

- 프론트: `react==18.3.1`, `three==0.169.0`, `@react-three/fiber==8.18.0`, `@react-three/drei==9.122.0`, `framer-motion==11.18.2`, `@radix-ui/react-dialog==1.3.1`, `tailwindcss==3.4.19`, `vite==5.4.21`, `typescript==5.9.3`
- API 서버: `fastapi==0.115.6`, `uvicorn==0.34.0`

## 통합 때 옮길 위치

| 지금 위치 | 옮길 곳 | 할 일 |
| --- | --- | --- |
| `curator_web/frontend/` | `frontend/` | `package.json`의 API 경로 수정 |
| `members/jongho/fastapi/` | `backend/api/` (knlee, 종호와 협의) | `service.py`의 경로 수정, `nlu.py`를 A.X 호출로 교체 |
| `curator_web/api_contract.json` | `docs/interface.md`에 정리 | 팀과 형식 합의, 변경 기록 작성 |

## 남은 작업

- FastAPI 코드의 커밋 시점을 종호와 정하기
- `hyeokjun/web-demo` PR 만들기 (리뷰어 knlee)
- `slot_eval/` 커밋 여부 정하기
- 팀원 데이터 받아서 파인튜닝 데이터 만들기, 학습 후 `nlu.py`에 A.X 연결
- 음료의 `26del)` 상품 10개가 무슨 표시인지 knlee에게 확인하기
