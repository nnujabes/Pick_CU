"""Pick CU API. 형식은 members/hyeokjun/curator_web/api_contract.json을 따른다.

실행: python -m uvicorn main:app --app-dir members/jongho/fastapi --port 8000 (저장소 루트에서)
POST /recommend?mock=<경우>를 붙이면 mock_responses.json의 응답을 그대로 돌려준다.
"""
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import review_store
import service

REPO_ROOT = Path(__file__).resolve().parents[3]
MOCK_PATH = REPO_ROOT / "members" / "hyeokjun" / "curator_web" / "frontend" / "src" / "mocks" / "mock_responses.json"
MockCase = Literal["single", "combo", "ask", "empty", "relaxed"]
SortKey = Literal["default", "price", "protein", "sugar", "calories", "sodium"]


@asynccontextmanager
async def lifespan(_app):
    review_store.init_db()
    service.load_parser_model()
    yield


app = FastAPI(title="Pick CU API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    categories: list[str] = Field(min_length=1, max_length=3)
    pending_text: str | None = Field(default=None, max_length=300)


class ReviewRequest(BaseModel):
    barcodes: list[str] = Field(min_length=1, max_length=30)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=200)
    query_text: str | None = Field(default=None, max_length=600)
    parsed_json: Any = None
    session_id: str = Field(min_length=8, max_length=64)


@app.get("/categories")
def get_categories():
    return service.list_categories()


@app.get("/products")
def get_products(
    category: str = "",
    q: str = Query(default="", max_length=50),
    sort: SortKey = "default",
    promo: Literal["", "1+1", "2+1"] = "",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    if category and category not in service.CATEGORIES:
        raise HTTPException(status_code=400, detail=f"없는 카테고리입니다: {category}")
    return service.list_products(category or None, q.strip(), sort, promo or None, page, size)


@app.post("/recommend")
def post_recommend(body: RecommendRequest, mock: MockCase | None = None):
    if mock:
        return json.loads(MOCK_PATH.read_text(encoding="utf-8"))[mock]
    try:
        return service.recommend_flow(body.text.strip(), body.categories, body.pending_text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/reviews")
def post_reviews(body: ReviewRequest):
    found = service.lookup_products(sorted(set(body.barcodes)))
    missing = [barcode for barcode in body.barcodes if barcode not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"없는 상품입니다: {missing}")
    review_id = review_store.save_review(
        body.barcodes, body.rating, body.comment.strip(), body.query_text, body.parsed_json, body.session_id,
    )
    return {"review_id": review_id, "product_stats": review_store.product_stats(sorted(set(body.barcodes)))}


@app.get("/reviews")
def get_reviews(
    barcode: str = "",
    combo_key: str = "",
    session_id: str = "",
    limit: int = Query(default=20, ge=1, le=100),
):
    return {"items": service.list_reviews_with_products(barcode, combo_key, session_id, limit)}
