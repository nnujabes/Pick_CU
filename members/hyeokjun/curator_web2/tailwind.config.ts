import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // 버튼 색 2개. cta(web1의 라임) = 주 기능(AI 추천받기)으로 명도·채도가 가장 높다.
      // 나머지 버튼은 기존 초록 계열을 쓴다: 장바구니는 테두리 강조, 선택된 카테고리는 명도·채도를 낮춰 채운다.
      colors: {
        cta: { DEFAULT: "#d4f27a", hover: "#e2f89e", ink: "#1b2109" },
      },
      fontFamily: {
        sans: ['"Apple SD Gothic Neo"', '"Malgun Gothic"', "system-ui", "sans-serif"],
      },
    },
  },
} satisfies Config;
