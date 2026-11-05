/** 저장소를 쓸 수 없는 환경에서도 화면이 동작하도록 실패를 삼킨다. */
function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 저장하지 못해도 이번 방문 동안은 계속 쓸 수 있다.
  }
}

export function readList<T>(key: string): T[] {
  try {
    const value: unknown = JSON.parse(read(key) ?? "[]");
    return Array.isArray(value) ? (value as T[]) : [];
  } catch {
    return [];
  }
}

export const writeList = (key: string, value: unknown[]) => write(key, JSON.stringify(value));

const SESSION_KEY = "pickcu2.session";
let memorySession: string | null = null;

/** 브라우저마다 만든 익명 ID. 저장소가 막혀 있으면 이번 방문 동안만 유지된다. */
export function getSessionId() {
  const saved = read(SESSION_KEY) ?? memorySession;
  if (saved) return saved;
  const created = window.crypto?.randomUUID?.() ?? `s-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
  memorySession = created;
  write(SESSION_KEY, created);
  return created;
}
