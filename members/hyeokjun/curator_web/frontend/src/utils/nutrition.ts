import type { Category, NutrientKey, Parsed } from "@/api/types";

export const CATEGORIES: Category[] = ["간편식사", "즉석조리", "과자류", "아이스크림", "식품", "음료"];

/** dv는 1일 영양성분 기준치다. */
export const NUTRIENTS: Record<NutrientKey, { ko: string; unit: string; dv: number }> = {
  calories: { ko: "열량", unit: "kcal", dv: 2000 },
  protein: { ko: "단백질", unit: "g", dv: 55 },
  sodium: { ko: "나트륨", unit: "mg", dv: 2000 },
  carbs: { ko: "탄수화물", unit: "g", dv: 324 },
  sugar: { ko: "당류", unit: "g", dv: 100 },
  fat: { ko: "지방", unit: "g", dv: 54 },
};
export const NUTRIENT_KEYS = Object.keys(NUTRIENTS) as NutrientKey[];

export const formatNumber = (value: number) => value.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
export const formatWon = (value: number) => `${value.toLocaleString("ko-KR")}원`;
export const formatNutrient = (key: NutrientKey, value: number) => `${formatNumber(value)}${NUTRIENTS[key].unit}`;
export const dailyPercent = (key: NutrientKey, value: number) => Math.round((value / NUTRIENTS[key].dv) * 100);

export function activeConditions(parsed: Parsed) {
  return NUTRIENT_KEYS.flatMap((key) => {
    const direction = parsed.nutrients[key];
    return direction ? [{ key, direction }] : [];
  });
}

/** "득템)뉴닭가슴살훈제" → 브랜드 "득템", 이름 "뉴닭가슴살훈제" */
export function splitBrand(productName: string) {
  const match = productName.match(/^([^)]{1,10})\)(.+)$/);
  return match ? { brand: match[1], name: match[2] } : { brand: null, name: productName };
}
