# Pick CU 웹 화면

원본은 `members/hyeokjun/curator_web2`입니다.

`web_dashboard.tsx`의 어두운 네온 화면을 바탕으로 만든 화면입니다. 3D 모형 없이 카테고리 선택, 조건 입력, 추천 목록, 별점 랭킹, 장바구니로 이루어져 있습니다.

추천과 별점은 `backend/api`의 실제 API를 씁니다.

## 실행

Node.js와 Python이 필요합니다. Python 패키지를 설치한 적이 없으면 `pip install -r ../backend/requirements.txt`를 먼저 실행합니다. `npm start`는 그 환경의 `python`으로 API를 띄우므로, 패키지를 설치한 Python 환경(예: conda)을 먼저 활성화합니다.

```bash
cd frontend
npm install
npm start
```

브라우저에서 http://localhost:5173 를 엽니다.

API를 따로 띄워 두었으면(`backend`에서 `python -m uvicorn api.main:app --port 8000`) 포트(8000)가 겹치므로 `npm start` 대신 `npm run dev`로 화면만 띄웁니다.

## 원본과 다른 점

| 원본 | 여기 |
| --- | --- |
| 예시 상품과 고정된 조합 5개 | `/recommend`의 실제 결과 |
| 예시 사진 | 상품 DB의 사진 |
| 예시 리뷰 | `/reviews`에 저장된 실제 별점 |
| 엔진 가동 표시 | 서버 연결 상태와 실제 문장 해석 방식 |
| 포켓CU 구매 버튼 | 뺌. 연동된 기능이 없어 "장바구니 비우기"로 바꿈 |

원본에 없던 되묻기, 결과 없음, 예산 넓힘 안내, 서버 오류 표시를 넣었습니다. 장바구니는 브라우저에 저장됩니다.
