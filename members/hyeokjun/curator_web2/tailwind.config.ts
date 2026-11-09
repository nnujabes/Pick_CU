import type { Config } from "tailwindcss";

/** 색 값은 globals.css의 CSS 변수에 있다. 다크가 기본이고 [data-theme="light"]에서 값만 바뀐다. */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;
const scale = (name: string, steps: number[]) =>
  Object.fromEntries(steps.map((step) => [step, token(`${name}-${step}`)]));

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // cta = 주 기능(AI 추천받기)의 바탕, cta-fg = 바탕 위 글자·아이콘으로 쓰는 강조색,
      // cta-mark = 선택 테두리와 체크 동그라미, soft = 선택된 카드 바탕, panel = 카드·입력창 바탕, page = 페이지 바탕.
      colors: {
        cta: {
          DEFAULT: token("cta"),
          hover: token("cta-hover"),
          ink: token("cta-ink"),
          soft: token("cta-soft"),
          fg: token("cta-fg"),
          mark: token("cta-mark"),
          check: token("cta-check"),
        },
        panel: { DEFAULT: token("panel"), line: token("panel-line") },
        page: token("page"),
        strong: token("strong"),
        "on-accent": token("on-accent"),
        accent: { DEFAULT: token("accent"), soft: token("accent-soft") },
        status: token("status"),
        star: token("star"),
        tip: token("tip"),
        drawer: token("drawer"),
        top: { a: token("top-a"), b: token("top-b"), c: token("top-c") },
        slate: scale("slate", [100, 200, 300, 400, 500, 600, 700, 800, 900, 950]),
        emerald: scale("emerald", [300, 400, 500, 800, 950]),
        amber: scale("amber", [200, 400, 500, 950]),
        rose: scale("rose", [200, 300, 400, 500, 950]),
        sky: scale("sky", [200, 500, 950]),
        purple: scale("purple", [300]),
      },
      fontFamily: {
        sans: ['"Apple SD Gothic Neo"', '"Malgun Gothic"', "system-ui", "sans-serif"],
      },
    },
  },
} satisfies Config;
