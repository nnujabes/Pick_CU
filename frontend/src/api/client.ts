import type { Category, Parsed, ProductPage, ProductPromo, ProductSort, RecommendResponse, SavedReview } from "./types";

const UNREACHABLE = "추천 서버에 연결하지 못했어요. API 서버가 켜져 있는지 확인해 주세요.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch {
    throw new Error(UNREACHABLE);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : UNREACHABLE);
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

export const postRecommend = (body: { text: string; categories: Category[]; pending_text: string | null }) =>
  postJson<RecommendResponse>("/recommend", body);

export const postReview = (body: {
  barcodes: string[];
  rating: number;
  comment: string;
  query_text: string | null;
  parsed_json: Parsed | null;
  session_id: string;
}) => postJson<unknown>("/reviews", body);

export const fetchReviews = () => request<{ items: SavedReview[] }>("/reviews?limit=100");

/** 전체 상품 목록. 카테고리·검색어·정렬·행사로 거르고 페이지 단위로 받는다. */
export function fetchProducts(
  params: { category: Category | ""; q: string; sort: ProductSort; promo: ProductPromo; page: number; size: number },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    category: params.category,
    q: params.q,
    sort: params.sort,
    promo: params.promo,
    page: String(params.page),
    size: String(params.size),
  });
  return request<ProductPage>(`/products?${query}`, { signal });
}
