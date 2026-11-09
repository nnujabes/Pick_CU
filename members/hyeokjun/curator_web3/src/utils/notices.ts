import type { NoNutrientReason, RecommendResponse } from "@/api/types";
import type { InputNotice } from "@/components/PromptForm";
import { formatWon } from "./format";

// 서버(members/jongho/fastapi/service.py)의 MIN_BUDGET과 같아야 한다.
const MIN_BUDGET = 1000;

const DEFAULT_NO_NUTRIENT = "영양소 정보를 알 수 없어요. 다시 입력해 주세요.";

const NO_NUTRIENT_TEXT: Record<NoNutrientReason, string> = {
  empty: "문장을 입력해 주세요.",
  too_long: "문장이 너무 길어요. 300자 이내로 줄여 주세요.",
  no_condition: "인사나 추천 요청만으로는 찾을 수 없어요. 상황이나 원하는 영양을 적어 주세요.",
  unrelated: "먹거리와 관련 없는 문장이에요. 상황이나 원하는 영양을 적어 주세요.",
  invalid_output: "문장을 이해하지 못했어요. 조금 다르게 적어 주세요.",
  error: "문장을 해석하다 문제가 생겼어요. 다시 시도해 주세요.",
};

/** 결과 없이 입력창 아래 안내로 끝나는 응답이면 그 안내를, 아니면 null을 돌려준다. */
export function noticeFor(response: RecommendResponse): InputNotice | null {
  if (response.status === "no_nutrient") {
    const text = (response.reason && NO_NUTRIENT_TEXT[response.reason]) || DEFAULT_NO_NUTRIENT;
    return { tone: "warn", text };
  }
  if (response.status === "budget_too_low") {
    const budget = response.parsed.budget;
    const prefix = budget ? `예산 ${formatWon(budget)}으로는 추천할 수 없어요.` : "예산이 너무 적어요.";
    return { tone: "warn", text: `${prefix} ${formatWon(MIN_BUDGET)} 이상으로 적어 주세요.` };
  }
  return null;
}
