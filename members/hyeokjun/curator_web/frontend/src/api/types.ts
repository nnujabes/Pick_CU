// api_contract.json과 같은 형식이다.
export type Category = "간편식사" | "즉석조리" | "과자류" | "아이스크림" | "식품" | "음료";
export type NutrientKey = "calories" | "protein" | "sodium" | "carbs" | "sugar" | "fat";
export type Direction = "high" | "low";
export type SortKey = "default" | "price" | "protein" | "sugar" | "calories" | "sodium";
export type PromoKey = "" | "1+1" | "2+1";

export interface Product extends Record<NutrientKey, number> {
  item_cd: string;
  category: Category;
  product_name: string;
  price: number;
  event_type: "NONE" | "1+1" | "2+1";
  image_url: string | null;
  avg_rating?: number | null;
  n_reviews?: number;
}

export interface Parsed {
  nutrients: Record<NutrientKey, Direction | null>;
  constraints: { nutrient: NutrientKey; op: string; value: number }[];
  budget: number | null;
  count: number | null;
  price_priority: boolean;
  need_clarification: boolean;
  clarification_question: string | null;
  issue: string | null;
}

export interface ResultRow {
  rank: number;
  total_score: number;
  nutrition_score: number;
  price_score: number | null;
  total_price: number;
  totals: Record<NutrientKey, number>;
  items: Product[];
}

export interface RecommendResponse {
  status: "ok" | "ask" | "empty";
  parsed: Parsed;
  goal: string | null;
  quick_replies: string[];
  mode: "단품" | "조합" | null;
  relaxed: { message: string; original_budget: number; used_budget: number } | null;
  notice: string | null;
  results: ResultRow[];
  source: "db" | "mock";
  parser: "rule" | "ax";
}

export interface CategorySummary {
  categories: { name: Category; count: number }[];
  total: number;
}

export interface ProductPage {
  total: number;
  page: number;
  size: number;
  items: Product[];
}

export interface ProductStat {
  barcode: string;
  avg_rating: number | null;
  n_reviews: number;
}

export interface SavedReview {
  id: number;
  combo_key: string;
  rating: number;
  comment: string | null;
  query_text: string | null;
  created_at: string;
  updated_at: string | null;
  barcodes: string[];
  items: { barcode: string; product_name: string | null; image_url: string | null; category: Category | null }[];
}
