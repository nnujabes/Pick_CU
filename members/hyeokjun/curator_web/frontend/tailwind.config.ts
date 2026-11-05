import type { Config } from "tailwindcss";

const FONT_BODY = ['"IBM Plex Sans KR"', '"Apple SD Gothic Neo"', '"Malgun Gothic"', "system-ui", "sans-serif"];
const FONT_MONO = ['"Nanum Gothic Coding"', '"D2Coding"', "Consolas", "ui-monospace", "monospace"];

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#232420",
        panel: "#2b2c27",
        "panel-2": "#33352f",
        line: "#41433b",
        fg: "#f1f2ec",
        muted: "#a6a89b",
        soft: "#d3d5ca",
        dim: "#7d7f74",
        lime: "#d4f27a",
        "lime-ink": "#1b2109",
        warm: "#f2b46a",
        alert: "#f39a86",
        sky: "#8fd0ea",
      },
      borderRadius: { card: "8px", btn: "4px", chip: "999px" },
      fontFamily: { sans: FONT_BODY, mono: FONT_MONO },
      keyframes: {
        shake: {
          "0%, 100%": { transform: "translateX(0)" },
          "20%, 60%": { transform: "translateX(-4px)" },
          "40%, 80%": { transform: "translateX(4px)" },
        },
      },
      animation: { shake: "shake 320ms ease-in-out" },
    },
  },
  plugins: [],
} satisfies Config;
