import type {
  Category,
  CategorySummary,
  MockCase,
  Parsed,
  ProductPage,
  ProductStat,
  PromoKey,
  RecommendResponse,
  SavedReview,
  SortKey,
} from "./types";

const BASE_URL = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `서버 오류 (${response.status})`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

function postJson<T>(path: string, body: unknown) {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const fetchCategories = () => request<CategorySummary>("/categories");

export function fetchProducts(
  params: { category: Category | ""; q: string; sort: SortKey; promo: PromoKey; page: number; size?: number },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    category: params.category,
    q: params.q,
    sort: params.sort,
    promo: params.promo,
    page: String(params.page),
    size: String(params.size ?? 20),
  });
  return request<ProductPage>(`/products?${query}`, { signal });
}

export function postRecommend(
  body: { text: string; categories: Category[]; pending_text: string | null },
  mock?: MockCase,
) {
  return postJson<RecommendResponse>(`/recommend${mock ? `?mock=${mock}` : ""}`, body);
}

export const postReview = (body: {
  barcodes: string[];
  rating: number;
  comment: string;
  query_text: string | null;
  parsed_json: Parsed | null;
  session_id: string;
}) => postJson<{ review_id: number; product_stats: ProductStat[] }>("/reviews", body);

export function fetchReviews(params: { barcode?: string; session_id?: string; limit?: number }, signal?: AbortSignal) {
  const query = new URLSearchParams({
    barcode: params.barcode ?? "",
    session_id: params.session_id ?? "",
    limit: String(params.limit ?? 20),
  });
  return request<{ items: SavedReview[] }>(`/reviews?${query}`, { signal });
}
