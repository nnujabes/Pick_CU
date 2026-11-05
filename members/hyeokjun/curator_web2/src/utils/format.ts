import type { Category, NutrientKey, Parsed, Product, ResultRow } from "@/api/types";

export const CATEGORIES: Category[] = ["간편식사", "즉석조리", "과자류", "아이스크림", "식품", "음료"];

export const NUTRIENTS: Record<NutrientKey, { ko: string; unit: string }> = {
  protein: { ko: "단백질", unit: "g" },
  calories: { ko: "열량", unit: "kcal" },
  sodium: { ko: "나트륨", unit: "mg" },
  carbs: { ko: "탄수화물", unit: "g" },
  sugar: { ko: "당류", unit: "g" },
  fat: { ko: "지방", unit: "g" },
};
export const NUTRIENT_KEYS = Object.keys(NUTRIENTS) as NutrientKey[];

const formatNumber = (value: number) => value.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
export const formatWon = (value: number) => `${value.toLocaleString("ko-KR")}원`;
export const formatNutrient = (key: NutrientKey, value: number) => `${formatNumber(value)}${NUTRIENTS[key].unit}`;

/** "득템)뉴닭가슴살훈제" → "뉴닭가슴살훈제" */
export const shortName = (productName: string) => productName.match(/^[^)]{1,10}\)(.+)$/)?.[1] ?? productName;

export const comboKey = (items: Pick<Product, "item_cd">[]) =>
  [...new Set(items.map((item) => item.item_cd))].sort().join("|");

/** 서버가 조합 이름을 주지 않아 담긴 상품으로 만든다. */
export function comboTitle(row: ResultRow) {
  if (row.items.length === 1) return shortName(row.items[0].product_name);
  return `${[...new Set(row.items.map((item) => item.category))].join(" + ")} 조합`;
}

/** 서버가 해석한 조건을 그대로 보여 준다. */
export function conditionText(parsed: Parsed) {
  const parts = NUTRIENT_KEYS.flatMap((key) => {
    const direction = parsed.nutrients[key];
    return direction ? [`${NUTRIENTS[key].ko} ${direction === "high" ? "높게" : "낮게"}`] : [];
  });
  if (parsed.budget) parts.push(`${formatWon(parsed.budget)} 이하`);
  return parts.join(" · ");
}

export function activeNutrients(parsed: Parsed) {
  return NUTRIENT_KEYS.filter((key) => parsed.nutrients[key]);
}
