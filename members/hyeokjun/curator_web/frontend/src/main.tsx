import { MotionConfig, MotionGlobalConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AppStoreProvider } from "./store/AppStore";
import "./styles/globals.css";

MotionGlobalConfig.skipAnimations = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <AppStoreProvider>
        <App />
      </AppStoreProvider>
    </MotionConfig>
  </StrictMode>,
);
