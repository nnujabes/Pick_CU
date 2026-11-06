// curator_web/api_contract.json과 같은 형식이다.
export type Category = "간편식사" | "즉석조리" | "과자류" | "아이스크림" | "식품" | "음료";
export type NutrientKey = "calories" | "protein" | "sodium" | "carbs" | "sugar" | "fat";

export interface Product extends Record<NutrientKey, number> {
  item_cd: string;
  category: Category;
  product_name: string;
  price: number;
  event_type: "NONE" | "1+1" | "2+1";
  image_url: string | null;
}

export interface Parsed {
  nutrients: Record<NutrientKey, "high" | "low" | null>;
  budget: number | null;
  clarification_question: string | null;
}

export interface ResultRow {
  rank: number;
  total_price: number;
  totals: Record<NutrientKey, number>;
  items: Product[];
}

export interface RecommendResponse {
  // no_nutrient: 문장에서 영양소 정보를 찾지 못함(A.X parse_query가 None). 입력창 아래에 안내한다.
  status: "ok" | "ask" | "empty" | "no_nutrient";
  parsed: Parsed;
  goal: string | null;
  quick_replies: string[];
  mode: "단품" | "조합" | null;
  relaxed: { message: string } | null;
  notice: string | null;
  results: ResultRow[];
  parser: "rule" | "ax";
}

export interface SavedReview {
  id: number;
  combo_key: string;
  rating: number;
  comment: string | null;
  created_at: string;
  updated_at: string | null;
  items: { barcode: string; product_name: string | null }[];
}
