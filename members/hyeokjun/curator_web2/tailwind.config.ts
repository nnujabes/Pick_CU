import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // 시안(절제된 다크 사이버펑크)의 민트. cta = 주 기능(AI 추천받기)과 선택 표시.
      // soft = 선택된 카테고리 카드 바탕, panel = 카드·입력창 바탕, page = 페이지 바탕.
      colors: {
        cta: { DEFAULT: "#4fd8a8", hover: "#6fe3bb", ink: "#05261a", soft: "#11302a" },
        panel: { DEFAULT: "#131a24", line: "#2a3342" },
        page: "#0d121a",
      },
      fontFamily: {
        sans: ['"Apple SD Gothic Neo"', '"Malgun Gothic"', "system-ui", "sans-serif"],
      },
    },
  },
} satisfies Config;
