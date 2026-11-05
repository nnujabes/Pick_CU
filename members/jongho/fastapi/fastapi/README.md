# Pick CU API (FastAPI)

웹 화면(`members/hyeokjun/curator_web/frontend`)이 호출하는 API 서버입니다. 팀 필터 엔진(`backend/pickcu/`)과 상품 DB(`backend/data/cu_products.db`)는 읽기만 합니다.

## 실행

```bash
pip install -r members/jongho/fastapi/requirements.txt
python -m uvicorn main:app --app-dir members/jongho/fastapi --port 8000
```

API 문서는 http://127.0.0.1:8000/docs 에서 볼 수 있습니다. 화면과 함께 켜려면 `members/hyeokjun/curator_web/frontend`에서 `npm start`를 실행합니다.

## 테스트

```bash
python -m unittest discover -s members/jongho/fastapi -p "test_*.py"
```

## 파일

| 파일 | 역할 |
| --- | --- |
| `main.py` | API 경로. 형식은 `members/hyeokjun/curator_web/api_contract.json` |
| `service.py` | 팀 엔진과 상품 DB 호출, 응답 형식 변환, 리뷰 점수 반영 |
| `nlu.py` | 문장 해석 임시 규칙. A.X 4.0 Light를 연결하면 `parse_request`만 교체 |
| `review_store.py` | 리뷰 저장. `data/reviews.db`는 자동으로 만들어지고 커밋되지 않음 |
| `build_mocks.py` | 프론트의 `mock_responses.json` 생성 |
| `test_api.py` | API 테스트 |
