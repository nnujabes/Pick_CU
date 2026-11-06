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

/** no_nutrient의 이유. 서버가 보내지 않으면 null이고, 화면은 기본 문구를 쓴다. */
export type NoNutrientReason =
  | "empty" // 빈 입력
  | "too_long" // 300자 초과
  | "no_condition" // 인삿말·잡담·일반 요청어만 있음 (모델 호출 전 규칙)
  | "unrelated" // 모델이 관계없는 문장으로 판단 ({"nutrients": []})
  | "invalid_output" // 모델 출력 형식 오류
  | "error"; // 실행 중 오류

export interface RecommendResponse {
  // no_nutrient: 문장에서 영양소 정보를 찾지 못함(parse_query가 None). budget_too_low: 예산이 최소 금액 미만.
  // 둘 다 결과 없이 입력창 아래에 안내한다.
  status: "ok" | "ask" | "empty" | "no_nutrient" | "budget_too_low";
  reason?: NoNutrientReason | null;
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
