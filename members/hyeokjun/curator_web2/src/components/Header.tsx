import { LayoutGrid, ShoppingCart, Store, TrendingUp } from "lucide-react";

export type ServerState = "checking" | "up" | "down";
export type Tab = "home" | "ratings" | "products";

interface Props {
  activeTab: Tab;
  cartCount: number;
  server: ServerState;
  parser: "rule" | "ax" | null;
  onHome: () => void;
  onRatings: () => void;
  onCart: () => void;
  onProducts: () => void;
}

/** 지어낸 엔진 이름 대신 서버가 실제로 알려 준 상태만 표시한다. */
function statusText(server: ServerState, parser: Props["parser"]) {
  if (server === "checking") return "서버 확인 중";
  if (server === "down") return "서버 연결 안 됨";
  if (parser === "ax") return "서버 연결됨 · A.X 문장 해석";
  if (parser === "rule") return "서버 연결됨 · 규칙 기반 문장 해석";
  return "서버 연결됨";
}

export function Header({ activeTab, cartCount, server, parser, onHome, onRatings, onCart, onProducts }: Props) {
  return (
    <header className="sticky top-0 z-40 border-b border-panel-line/70 bg-page/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1480px] items-center justify-between px-4 sm:px-8">
        <div className="flex h-full items-center gap-4 sm:gap-6">
          <button onClick={onHome} className="flex items-center gap-2.5" aria-label="메인 화면으로">
            <Store className="h-7 w-7 text-cta" strokeWidth={1.75} />
            <span className="hidden whitespace-nowrap text-lg font-extrabold text-white sm:inline">영양 편의점</span>
          </button>
          <span className="hidden h-4 w-px bg-slate-600 sm:block" aria-hidden />
          <button
            onClick={onRatings}
            aria-current={activeTab === "ratings" ? "page" : undefined}
            className={`relative flex h-full items-center gap-2 px-1 text-sm font-semibold transition-colors ${
              activeTab === "ratings" ? "text-white" : "text-slate-300 hover:text-white"
            }`}
          >
            <TrendingUp className="h-5 w-5 text-cta" />
            <span className="whitespace-nowrap">추천 메뉴</span>
            {activeTab === "ratings" && <span className="absolute inset-x-0 bottom-0 h-[3px] rounded-full bg-cta" />}
          </button>
          <button onClick={onCart} className="flex h-full items-center gap-2 text-sm font-semibold text-slate-300 transition-colors hover:text-white">
            <ShoppingCart className="h-5 w-5" />
            <span className="whitespace-nowrap">장바구니</span>
            {cartCount > 0 && (
              <span className="rounded-full bg-cta px-1.5 text-xs font-extrabold text-cta-ink">{cartCount}</span>
            )}
          </button>
          <button
            onClick={onProducts}
            aria-current={activeTab === "products" ? "page" : undefined}
            className={`relative flex h-full items-center gap-2 px-1 text-sm font-semibold transition-colors ${
              activeTab === "products" ? "text-white" : "text-slate-300 hover:text-white"
            }`}
          >
            <LayoutGrid className="h-5 w-5" />
            <span className="whitespace-nowrap">전체 상품</span>
            {activeTab === "products" && <span className="absolute inset-x-0 bottom-0 h-[3px] rounded-full bg-cta" />}
          </button>
        </div>

        <div className="hidden items-center gap-2 text-sm text-slate-300 sm:flex" data-testid="server-status">
          <span className="relative flex h-2 w-2">
            {server === "up" && (
              <span className="absolute inline-flex h-full w-full rounded-full bg-cta opacity-75 motion-safe:animate-ping" />
            )}
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                server === "up" ? "bg-cta" : server === "down" ? "bg-rose-400" : "bg-slate-500"
              }`}
            />
          </span>
          <span>{statusText(server, parser)}</span>
        </div>
      </div>
    </header>
  );
}
