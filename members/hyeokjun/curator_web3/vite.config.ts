import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    // curator_web(5173), curator_web2(5174)와 함께 띄울 수 있게 포트를 나눈다.
    port: 5175,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        rewrite: (url) => url.replace(/^\/api/, ""),
      },
    },
  },
});
