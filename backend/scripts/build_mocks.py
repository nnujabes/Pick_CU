"""mock 응답 5종을 실제 DB와 엔진 결과로 만들어 프론트의 mock_responses.json에 저장한다.

DB가 바뀌었을 때만 다시 실행한다 (저장소 루트에서): python backend/scripts/build_mocks.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.main import MOCK_PATH  # noqa: E402
from api.service import recommend_flow  # noqa: E402

CASES = {
    "single": ("단백질 많은 음료", ["음료"]),
    "combo": ("운동 후에 먹을 거 8천원", ["간편식사", "음료"]),
    "ask": ("뭐 먹지", ["식품", "음료"]),
    "empty": ("단백질 많이 1000원", ["과자류", "음료", "식품"]),
    "relaxed": ("단백질 많이 1400원", ["과자류", "음료", "식품"]),
}
EXPECTED_STATUS = {"single": "ok", "combo": "ok", "ask": "ask", "empty": "empty", "relaxed": "ok"}


def main():
    responses = {}
    for case, (text, categories) in CASES.items():
        response = recommend_flow(text, categories)
        assert response["status"] == EXPECTED_STATUS[case], case
        responses[case] = {**response, "source": "mock"}
    assert responses["relaxed"]["relaxed"], "조건 완화 경우가 완화 없이 끝났습니다."
    MOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    MOCK_PATH.write_text(json.dumps(responses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"저장: {MOCK_PATH}")


if __name__ == "__main__":
    main()
