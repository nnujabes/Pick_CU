import { Canvas } from "@react-three/fiber";
import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Category } from "@/api/types";
import { useReducedMotion } from "@/hooks/useMedia";
import { CATEGORIES } from "@/utils/nutrition";
import { StoreRoom, type TipEvent } from "./scene/StoreRoom";

interface Props {
  selected: Category[];
  pinned: Partial<Record<Category, number>>;
  focused: Category | null;
  highlighted: Category[];
  counts: Partial<Record<Category, number>>;
  onOpen: (category: Category) => void;
}

function supportsWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

class SceneBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function SceneFallback() {
  return (
    <div className="relative h-full w-full">
      <img src="/store-fallback.png" alt="편의점 진열대 6개가 있는 아이소메트릭 모형" className="h-full w-full object-contain" />
      <p className="absolute left-3 top-3 font-mono text-xs text-muted">아래 버튼으로 진열대를 둘러볼 수 있어요.</p>
    </div>
  );
}

export function Scene3D({ selected, pinned, focused, highlighted, counts, onOpen }: Props) {
  const reduced = useReducedMotion();
  const webgl = useMemo(supportsWebGL, []);
  const regionRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  const [tabVisible, setTabVisible] = useState(!document.hidden);
  const [tip, setTip] = useState<TipEvent | null>(null);
  const [tapped, setTapped] = useState<Category | null>(null);
  const touchOnly = useRef(window.matchMedia("(hover: none)").matches);

  useEffect(() => {
    const region = regionRef.current;
    if (!region) return;
    const observer = new IntersectionObserver((entries) => setVisible(entries[0].isIntersecting));
    observer.observe(region);
    const onVisibility = () => setTabVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    document.body.style.cursor = tip && !touchOnly.current ? "pointer" : "";
    return () => {
      document.body.style.cursor = "";
    };
  }, [tip]);

  function activate(event: TipEvent) {
    if (touchOnly.current && tapped !== event.category) {
      setTapped(event.category);
      setTip(event);
      return;
    }
    setTapped(null);
    setTip(null);
    onOpen(event.category);
  }

  const running = visible && tabVisible;
  const frameloop = !running ? "never" : reduced ? "demand" : "always";
  const fallback = <SceneFallback />;

  const region = regionRef.current?.getBoundingClientRect();
  const tipLeft = tip && region ? Math.min(Math.max(tip.clientX - region.left, 120), region.width - 120) : 0;
  const tipTop = tip && region ? Math.max(tip.clientY - region.top, 44) : 0;

  return (
    <div data-scene-box className="scene-box flex flex-col overflow-hidden rounded-card border border-line bg-[#191a17]">
      <div
        ref={regionRef}
        className="relative min-h-0 flex-1 overflow-hidden"
        onClick={(event) => {
          if (event.target === regionRef.current) {
            setTip(null);
            setTapped(null);
          }
        }}
      >
        <div className="absolute inset-0">
          {webgl ? (
            <SceneBoundary fallback={fallback}>
              <Canvas
                flat
                shadows="soft"
                dpr={[1, 2]}
                frameloop={frameloop}
                gl={{ antialias: true, alpha: true }}
                onPointerMissed={() => {
                  setTip(null);
                  setTapped(null);
                }}
              >
                <StoreRoom
                  selected={selected}
                  pinned={pinned}
                  focused={focused}
                  highlighted={highlighted}
                  hovered={tip?.category ?? null}
                  reduced={reduced}
                  onHover={setTip}
                  onActivate={activate}
                />
              </Canvas>
            </SceneBoundary>
          ) : (
            fallback
          )}
        </div>
        {tip && (
          <div
            role="tooltip"
            className="tnum pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[130%] whitespace-nowrap rounded-btn bg-fg px-3 py-2 font-mono text-xs text-[#1d1e1a]"
            style={{ left: tipLeft, top: tipTop }}
          >
            <b>{tip.category}</b>
            {counts[tip.category] != null && ` · ${counts[tip.category]!.toLocaleString("ko-KR")}개`}
            {pinned[tip.category] ? ` · 추천 ${pinned[tip.category]}개` : ""}
            {touchOnly.current ? " · 한 번 더 누르면 둘러보기" : " · 클릭해서 둘러보기"}
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-line bg-panel px-3 py-2" role="group" aria-label="진열대 바로가기">
        <span className="mr-1 font-mono text-xs text-dim">진열대</span>
        {CATEGORIES.map((category) => (
          <button
            key={category}
            type="button"
            onClick={() => onOpen(category)}
            className="rounded-btn border border-line px-2 py-1 font-mono text-xs text-muted transition-colors hover:border-muted hover:text-fg"
          >
            {category}
          </button>
        ))}
      </div>
    </div>
  );
}
