import { useEffect, useState } from "react";

// A.X 문장 해석이 한 문장에 3초쯤 걸려서, 기다리는 동안 단계별로 안내를 바꾼다.
const STEPS = [
  { after: 0, text: "문장을 해석하는 중이에요…" },
  { after: 3000, text: "조건에 맞는 상품을 찾는 중이에요…" },
  { after: 10000, text: "조금 오래 걸리고 있어요. 잠시만 기다려 주세요." },
];

export function useLoadingMessage(loading: boolean) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    setStep(0);
    if (!loading) return;
    const timers = STEPS.slice(1).map((item, index) => window.setTimeout(() => setStep(index + 1), item.after));
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [loading]);

  return STEPS[step].text;
}
