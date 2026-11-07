import type { Category, NutrientKey, Parsed, Product, ResultRow } from "@/api/types";

export const CATEGORIES: Category[] = ["간편식사", "즉석조리", "과자류", "아이스크림", "식품", "음료"];

/** 카테고리마다 들어 있는 CU 세부 분류. 카테고리에 마우스를 올리면 보여 준다. */
export const CATEGORY_DETAILS: Record<Category, string[]> = {
  간편식사: ["도시락", "샌드위치/햄버거", "주먹밥/김밥"],
  즉석조리: ["튀김류", "즉석커피"],
  과자류: ["스낵/비스켓", "빵/디저트", "껌/초콜릿/캔디"],
  아이스크림: ["아이스크림"],
  식품: ["가공식사", "안주류", "식재료"],
  음료: ["음료", "아이스드링크", "유제품"],
};

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
