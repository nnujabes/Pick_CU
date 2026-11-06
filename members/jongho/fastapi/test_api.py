"""실행 (저장소 루트에서): python -m unittest discover -s members/jongho/fastapi -p "test_*.py"

기존 테스트는 규칙 파서 기준이다. A.X 테스트는 모델을 불러오지 못하면 건너뛴다.
"""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

os.environ["PICKCU_PARSER"] = "rule"

from fastapi.testclient import TestClient

import review_store
import service
import query_parser  # service가 불러올 경로를 추가한 뒤에 불러온다
from main import app
from pickcu.filter_engine import recommend

client = TestClient(app)
SESSION = "test-session-1"


def post(text, categories, **params):
    return client.post("/recommend", params=params, json={"text": text, "categories": categories})


def review(barcodes, rating, session=SESSION, comment="좋아요"):
    return client.post("/reviews", json={
        "barcodes": barcodes, "rating": rating, "comment": comment,
        "query_text": "단백질", "parsed_json": {"budget": None}, "session_id": session,
    })


class IsolatedReviewDb(unittest.TestCase):
    """테스트마다 빈 리뷰 DB를 쓴다. 시연 데이터는 건드리지 않는다."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db_path = Path(folder.name) / "data" / "reviews.db"
        patch = mock.patch.object(review_store, "REVIEW_DB", self.db_path)
        patch.start()
        self.addCleanup(patch.stop)


class ProductsTest(IsolatedReviewDb):
    def test_categories_match_db(self):
        body = client.get("/categories").json()
        self.assertEqual(body["total"], 2154)
        self.assertEqual(len(body["categories"]), 6)

    def test_page_and_sort(self):
        first = client.get("/products", params={"category": "음료", "sort": "price", "page": 1}).json()
        second = client.get("/products", params={"category": "음료", "sort": "price", "page": 2}).json()
        prices = [item["price"] for item in first["items"]]
        self.assertEqual(len(prices), 20)
        self.assertEqual(prices, sorted(prices))
        self.assertFalse({i["item_cd"] for i in first["items"]} & {i["item_cd"] for i in second["items"]})

    def test_all_categories_and_promo(self):
        body = client.get("/products", params={"category": "", "size": 1}).json()
        self.assertEqual(body["total"], 2154)
        promo = client.get("/products", params={"promo": "1+1", "size": 100}).json()
        self.assertEqual(promo["total"], 223)
        self.assertTrue(all(item["event_type"] == "1+1" for item in promo["items"]))

    def test_item_has_image_and_stats(self):
        item = client.get("/products", params={"size": 1}).json()["items"][0]
        self.assertIn("image_url", item)
        self.assertNotIn("thumbnail_url", item)
        self.assertEqual((item["avg_rating"], item["n_reviews"]), (None, 0))

    def test_search_treats_percent_as_text(self):
        body = client.get("/products", params={"category": "음료", "q": "%%없는상품%%"}).json()
        self.assertEqual(body["total"], 0)

    def test_unknown_category_is_rejected(self):
        self.assertEqual(client.get("/products", params={"category": "없음"}).status_code, 400)


class RecommendTest(IsolatedReviewDb):
    def test_without_reviews_matches_team_engine(self):
        nutrients = {"단백질": "high", "지방": "low", "당류": "low"}
        ours = service.recommend_with_reviews(["간편식사", "음료"], nutrients, budget=8000)
        theirs = recommend(["간편식사", "음료"], nutrients, budget=8000)
        self.assertEqual(ours, theirs)

    def test_single_uses_real_products(self):
        body = post("단백질 많은 음료", ["음료"]).json()
        self.assertEqual((body["status"], body["mode"], body["source"]), ("ok", "단품", "db"))
        self.assertEqual(len(body["results"]), 5)
        first = body["results"][0]
        self.assertEqual(first["totals"]["protein"], first["items"][0]["protein"])
        self.assertIn("image_url", first["items"][0])
        self.assertIn("n_reviews", first["items"][0])

    def test_combo_stays_within_budget(self):
        body = post("운동 후에 먹을 거 8천원", ["간편식사", "음료"]).json()
        self.assertEqual(body["mode"], "조합")
        self.assertEqual(body["parsed"]["nutrients"]["sugar"], "low")
        self.assertTrue(all(row["total_price"] <= 8000 for row in body["results"]))

    def test_ask_then_answer(self):
        ask = post("뭐 먹지", ["식품"]).json()
        self.assertEqual(ask["status"], "ask")
        self.assertTrue(ask["quick_replies"])
        answer = client.post("/recommend", json={
            "text": ask["quick_replies"][0], "categories": ["식품"], "pending_text": "뭐 먹지",
        }).json()
        self.assertEqual(answer["status"], "ok")

    def test_after_workout_is_not_asked(self):
        body = post("운동 끝났는데 뭐 먹지", ["식품"]).json()
        self.assertEqual((body["status"], body["goal"]), ("ok", "운동 후"))

    def test_before_workout_wants_carbs(self):
        for text in ("운동전에 먹을 거", "운동하기 전에 먹을 거"):
            body = post(text, ["식품"]).json()
            self.assertEqual((body["status"], body["goal"]), ("ok", None), text)
            self.assertEqual(body["parsed"]["nutrients"]["carbs"], "high", text)

    def test_no_workout_words_are_asked(self):
        for text in ("운동 안 했어 뭐 먹지", "운동화 신고 나왔는데 뭐 먹지"):
            self.assertEqual(post(text, ["식품"]).json()["status"], "ask", text)

    def test_budget_alone_is_asked_and_kept_after_answer(self):
        ask = post("1만원으로 뭐 먹지", ["식품"]).json()
        self.assertEqual((ask["status"], ask["parsed"]["budget"]), ("ask", 10000))
        answer = client.post("/recommend", json={
            "text": "든든하게", "categories": ["식품"], "pending_text": "1만원으로 뭐 먹지",
        }).json()
        self.assertEqual((answer["status"], answer["parsed"]["budget"]), ("ok", 10000))

    def test_empty_and_relaxed(self):
        self.assertEqual(post("단백질 많이 1000원", ["과자류", "음료", "식품"]).json()["status"], "empty")
        relaxed = post("단백질 많이 1400원", ["과자류", "음료", "식품"]).json()
        self.assertEqual(relaxed["relaxed"]["used_budget"], 1540)
        self.assertTrue(all(row["total_price"] <= 1540 for row in relaxed["results"]))

    def test_every_mock_case_is_served_with_images(self):
        for case, status in {"single": "ok", "combo": "ok", "ask": "ask", "empty": "empty", "relaxed": "ok"}.items():
            body = post("무시되는 문장", ["음료"], mock=case).json()
            self.assertEqual((body["status"], body["source"]), (status, "mock"), case)
            for row in body["results"]:
                self.assertTrue(all("image_url" in item for item in row["items"]))

    def test_reason_is_null_for_other_statuses(self):
        cases = {
            "ok": ("단백질 많은 음료", ["음료"]),
            "ask": ("뭐 먹지", ["식품"]),
            "empty": ("단백질 많이 1000원", ["과자류", "음료", "식품"]),
            "budget_too_low": ("500원으로 뭐 먹지", ["식품"]),
        }
        for status, (text, categories) in cases.items():
            body = post(text, categories).json()
            self.assertEqual(body["status"], status)
            self.assertIn("reason", body, status)
            self.assertIsNone(body["reason"], status)

    def test_rule_parser_budget_below_minimum(self):
        body = post("500원으로 뭐 먹지", ["식품"]).json()
        self.assertEqual((body["status"], body["parser"], body["parsed"]["budget"]), ("budget_too_low", "rule", 500))

    def test_too_many_categories_are_rejected(self):
        self.assertEqual(post("단백질", ["음료", "식품", "과자류", "아이스크림"]).status_code, 422)

    def test_good_reviews_raise_a_product(self):
        before = post("단백질 많은 음료", ["음료"]).json()["results"]
        fifth = before[4]["items"][0]["item_cd"]
        for index in range(30):
            self.assertEqual(review([fifth], 5, session=f"session-{index:04d}").status_code, 200)
        low = before[0]["items"][0]["item_cd"]
        for index in range(30):
            review([low], 1, session=f"other-{index:04d}")
        after = [row["items"][0]["item_cd"] for row in post("단백질 많은 음료", ["음료"]).json()["results"]]
        self.assertLess(after.index(fifth), 4)
        self.assertGreater(after.index(low) if low in after else 5, 0)


class ParserSelectionTest(IsolatedReviewDb):
    """모델 없이 parse_query 결과만 바꿔 파서 선택을 확인한다."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(service, "MODEL_READY", True)
        patch.start()
        self.addCleanup(patch.stop)
        # 하영의 parse_query_with_reason이 들어와도 이 테스트들이 실제 모델을 부르지 않게 지운다.
        without_reason = mock.patch.dict(vars(query_parser))
        without_reason.start()
        self.addCleanup(without_reason.stop)
        vars(query_parser).pop("parse_query_with_reason", None)

    def test_reason_from_parser_is_returned(self):
        for reason in ("no_condition", "unrelated"):
            with mock.patch.object(query_parser, "parse_query_with_reason", return_value=(None, reason), create=True):
                body = post("안녕하세요", ["음료"]).json()
            self.assertEqual((body["status"], body["parser"], body["reason"]), ("no_nutrient", "ax", reason))

    def test_found_result_from_detailed_parser_has_null_reason(self):
        result = {"budget": 5000, "nutrients": {"단백질": "high", "지방": "low"}}
        with mock.patch.object(query_parser, "parse_query_with_reason", return_value=(result, None), create=True):
            body = post("5천원 이하로 운동 후에 먹을 거", ["간편식사", "음료"]).json()
        self.assertEqual((body["status"], body["parser"], body["reason"]), ("ok", "ax", None))

    def test_without_detailed_parser_reason_is_null(self):
        self.assertFalse(hasattr(query_parser, "parse_query_with_reason"))
        with mock.patch.object(query_parser, "parse_query", return_value=None):
            body = post("안녕하세요", ["음료"]).json()
        self.assertEqual((body["status"], body["reason"]), ("no_nutrient", None))

    def test_budget_too_low_has_null_reason(self):
        result = {"budget": 500, "nutrients": {"단백질": "high", "지방": "low"}}
        with mock.patch.object(query_parser, "parse_query", return_value=result):
            body = post("500원으로 운동 후에 먹을 거", ["음료"]).json()
        self.assertEqual((body["status"], body["reason"]), ("budget_too_low", None))

    def test_model_result_is_used(self):
        result = {"budget": 3000, "nutrients": {"열량": "low", "단백질": "high"}}
        with mock.patch.object(query_parser, "parse_query", return_value=result):
            body = post("추천해줘 가성비 두 개", ["간편식사", "음료"]).json()
        self.assertEqual((body["status"], body["parser"], body["goal"]), ("ok", "ax", None))
        self.assertEqual(body["parsed"]["budget"], 3000)
        self.assertEqual(body["parsed"]["nutrients"], {
            "calories": "low", "carbs": None, "protein": "high", "fat": None, "sugar": None, "sodium": None,
        })
        self.assertEqual((body["parsed"]["count"], body["parsed"]["price_priority"]), (2, True))
        self.assertFalse(body["parsed"]["need_clarification"])

    def test_none_returns_no_nutrient(self):
        with mock.patch.object(query_parser, "parse_query", return_value=None):
            body = post("안녕", ["음료"]).json()
        self.assertEqual((body["status"], body["parser"], body["results"]), ("no_nutrient", "ax", []))
        self.assertEqual((body["mode"], body["quick_replies"], body["goal"]), (None, [], None))
        self.assertFalse(body["parsed"]["need_clarification"])
        self.assertEqual(set(body["parsed"]["nutrients"].values()), {None})

    def test_none_does_not_use_rule_nutrients(self):
        with mock.patch.object(query_parser, "parse_query", return_value=None):
            body = post("단백질 많은 음료 5천원", ["음료"]).json()
        self.assertEqual((body["status"], body["parser"]), ("no_nutrient", "ax"))
        self.assertEqual(set(body["parsed"]["nutrients"].values()), {None})
        self.assertEqual(body["parsed"]["budget"], 5000)

    def test_found_nutrients_return_ok(self):
        result = {"budget": 5000, "nutrients": {"단백질": "high", "지방": "low"}}
        with mock.patch.object(query_parser, "parse_query", return_value=result):
            body = post("5천원 이하로 운동 후에 먹을 거", ["간편식사", "음료"]).json()
        self.assertEqual((body["status"], body["parser"]), ("ok", "ax"))

    def test_budget_below_minimum_returns_budget_too_low(self):
        for budget in (0, 1, 999):
            result = {"budget": budget, "nutrients": {"단백질": "high", "지방": "low"}}
            with mock.patch.object(query_parser, "parse_query", return_value=result):
                body = post("운동 후에 먹을 거", ["음료"]).json()
            self.assertEqual((body["status"], body["parser"], body["results"]), ("budget_too_low", "ax", []), budget)
            self.assertEqual(body["parsed"]["budget"], budget)

    def test_minimum_budget_is_allowed(self):
        result = {"budget": 1000, "nutrients": {"단백질": "high", "지방": "low"}}
        with mock.patch.object(query_parser, "parse_query", return_value=result):
            body = post("운동 후에 먹을 거", ["음료"]).json()
        self.assertNotEqual(body["status"], "budget_too_low")

    def test_no_nutrient_comes_before_budget_too_low(self):
        with mock.patch.object(query_parser, "parse_query", return_value=None):
            body = post("500원", ["음료"]).json()
        self.assertEqual(body["status"], "no_nutrient")


class ParserLoadTest(unittest.TestCase):
    def test_rule_setting_does_not_load_model(self):
        with mock.patch.object(query_parser, "load_model") as load, mock.patch.object(service, "MODEL_READY", False):
            service.load_parser_model()
            load.assert_not_called()
            self.assertFalse(service.MODEL_READY)

    def test_load_failure_keeps_rule_parser(self):
        with mock.patch.dict(os.environ, {"PICKCU_PARSER": "ax"}), mock.patch.object(service, "MODEL_READY", False), \
                mock.patch.object(query_parser, "load_model", side_effect=RuntimeError("GPU 없음")), mock.patch("builtins.print"):
            service.load_parser_model()
            self.assertFalse(service.MODEL_READY)


class AxParserTest(IsolatedReviewDb):
    """실제 A.X 결과. 규남의 total_test.ipynb 출력과 같아야 한다."""

    @classmethod
    def setUpClass(cls):
        try:
            query_parser.load_model()
        except Exception as error:
            raise unittest.SkipTest(f"A.X를 불러오지 못함: {error}")
        patch = mock.patch.object(service, "MODEL_READY", True)
        patch.start()
        cls.addClassCleanup(patch.stop)

    def test_after_workout_with_budget(self):
        body = post("5천원 이하로 운동 후에 먹을 거", ["간편식사", "음료"]).json()
        self.assertEqual((body["status"], body["parser"], body["parsed"]["budget"]), ("ok", "ax", 5000))
        self.assertEqual((body["parsed"]["nutrients"]["protein"], body["parsed"]["nutrients"]["fat"]), ("high", "low"))

    def test_blood_sugar_without_budget(self):
        body = post("요즘 혈당이 걱정돼요", ["과자류"]).json()
        self.assertEqual((body["parser"], body["parsed"]["budget"]), ("ax", None))
        self.assertEqual((body["parsed"]["nutrients"]["sugar"], body["parsed"]["nutrients"]["calories"]), ("low", "low"))


class ReviewTest(IsolatedReviewDb):
    def setUp(self):
        super().setUp()
        items = client.get("/products", params={"category": "음료", "size": 2}).json()["items"]
        self.first, self.second = items[0]["item_cd"], items[1]["item_cd"]

    def rows(self, table):
        with closing(sqlite3.connect(self.db_path)) as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_db_is_created_with_tables(self):
        review_store.init_db()
        self.assertTrue(self.db_path.exists())
        self.assertEqual((self.rows("reviews"), self.rows("review_items")), (0, 0))

    def test_review_updates_product_stats(self):
        body = review([self.first], 5).json()
        self.assertEqual(body["product_stats"], [{"barcode": self.first, "avg_rating": 5.0, "n_reviews": 1}])
        review([self.first], 2, session="another-session")
        item = client.get("/products", params={"category": "음료", "size": 1}).json()["items"][0]
        self.assertEqual((item["avg_rating"], item["n_reviews"]), (3.5, 2))

    def test_same_session_and_combo_updates_instead_of_inserting(self):
        first_id = review([self.first, self.second], 5, comment="처음").json()["review_id"]
        second_id = review([self.second, self.first], 2, comment="수정").json()["review_id"]
        self.assertEqual(first_id, second_id)
        self.assertEqual((self.rows("reviews"), self.rows("review_items")), (1, 2))
        saved = client.get("/reviews", params={"session_id": SESSION}).json()["items"][0]
        self.assertEqual((saved["rating"], saved["comment"]), (2, "수정"))
        self.assertIsNotNone(saved["updated_at"])

    def test_list_filters_and_combo_key(self):
        review([self.first], 4)
        review([self.first, self.second], 3)
        by_barcode = client.get("/reviews", params={"barcode": self.second}).json()["items"]
        self.assertEqual(len(by_barcode), 1)
        key = "|".join(sorted([self.first, self.second]))
        self.assertEqual(by_barcode[0]["combo_key"], key)
        self.assertEqual(len(client.get("/reviews", params={"combo_key": key}).json()["items"]), 1)
        self.assertEqual(len(client.get("/reviews", params={"session_id": SESSION}).json()["items"]), 2)
        self.assertEqual(client.get("/reviews", params={"session_id": "nobody-here"}).json()["items"], [])
        self.assertTrue(by_barcode[0]["items"][0]["product_name"])

    def test_reviews_of_removed_products_are_kept(self):
        review([self.first], 5)
        review_store_id = client.get("/reviews").json()["items"][0]["id"]
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            connection.execute("UPDATE review_items SET barcode = 'gone' WHERE review_id = ?", (review_store_id,))
            connection.execute("UPDATE reviews SET combo_key = 'gone' WHERE id = ?", (review_store_id,))
        items = client.get("/reviews", params={"barcode": "gone"}).json()["items"]
        self.assertEqual(items[0]["items"][0]["product_name"], None)

    def test_invalid_reviews_are_rejected(self):
        self.assertEqual(review(["없는코드"], 5).status_code, 400)
        self.assertEqual(review([self.first], 6).status_code, 422)
        self.assertEqual(review([self.first], 5, comment="가" * 201).status_code, 422)
        self.assertEqual(self.rows("reviews"), 0)


if __name__ == "__main__":
    unittest.main()
