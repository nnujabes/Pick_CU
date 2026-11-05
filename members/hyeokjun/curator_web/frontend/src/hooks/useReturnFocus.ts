import { useCallback, useRef } from "react";

/** 패널을 닫으면 열기 전에 포커스가 있던 곳으로 돌려보낸다. 트리거 없이 여는 Radix 대화 상자에 쓴다. */
export function useReturnFocus(open: boolean) {
  const wasOpen = useRef(false);
  const previous = useRef<HTMLElement | null>(null);
  // 패널이 포커스를 옮기기 전에 렌더 단계에서 기억한다.
  if (open && !wasOpen.current) previous.current = document.activeElement as HTMLElement | null;
  wasOpen.current = open;

  return useCallback((event: Event) => {
    event.preventDefault();
    if (previous.current?.isConnected) previous.current.focus({ preventScroll: true });
  }, []);
}
