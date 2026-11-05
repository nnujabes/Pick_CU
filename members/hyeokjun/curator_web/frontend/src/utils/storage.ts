/** 저장소를 쓸 수 없는 환경에서도 화면이 동작하도록 실패를 삼킨다. */
export function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStorage(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 저장하지 못해도 이번 화면에서는 계속 쓸 수 있다.
  }
}

const SESSION_KEY = "pickcu.session";
let memorySession: string | null = null;

/** 브라우저마다 만든 익명 ID. 저장소가 막혀 있으면 이번 방문 동안만 유지된다. */
export function getSessionId() {
  const saved = readStorage(SESSION_KEY) ?? memorySession;
  if (saved) return saved;
  const created = window.crypto?.randomUUID?.() ?? `s-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
  memorySession = created;
  writeStorage(SESSION_KEY, created);
  return created;
}
