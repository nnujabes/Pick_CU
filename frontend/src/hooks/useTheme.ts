import { useEffect, useState } from "react";
import { readValue, writeValue } from "@/utils/storage";

export type Theme = "dark" | "light";

// 첫 화면이 깜빡이지 않도록 index.html의 인라인 스크립트도 같은 키를 읽는다.
const THEME_KEY = "pickcu2.theme";
const THEME_COLOR: Record<Theme, string> = { dark: "#0b0e14", light: "#f7f9fb" };

const savedTheme = (): Theme => (readValue(THEME_KEY) === "light" ? "light" : "dark");

/** 다크가 기본이다. 고른 모드는 브라우저에 저장해 다음 방문에도 유지한다. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(savedTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[theme]);
    writeValue(THEME_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme((current) => (current === "dark" ? "light" : "dark"));
  return { theme, toggleTheme };
}
