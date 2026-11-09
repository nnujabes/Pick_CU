const PROMPT_WIDE = "운동 후 먹을 1만 원 미만의 음식을 추천해줘";
const PROMPT_PHONE = "운동 후 1만 원 미만 음식 추천";

/** 휴대폰 폭의 입력창에서 잘리지 않도록 짧은 문장을 쓴다. 폭은 부르는 시점 기준이다. */
export const defaultPrompt = () => (window.matchMedia("(max-width: 639px)").matches ? PROMPT_PHONE : PROMPT_WIDE);
