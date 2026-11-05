import { ShoppingCart, TrendingUp } from "lucide-react";

export type ServerState = "checking" | "up" | "down";

interface Props {
  activeTab: "home" | "ratings";
  cartCount: number;
  server: ServerState;
  parser: "rule" | "ax" | null;
  onRatings: () => void;
  onCart: () => void;
}

/** 지어낸 엔진 이름 대신 서버가 실제로 알려 준 상태만 표시한다. */
function statusText(server: ServerState, parser: Props["parser"]) {
  if (server === "checking") return "서버 확인 중";
  if (server === "down") return "서버 연결 안 됨";
  if (parser === "ax") return "서버 연결됨 · A.X 문장 해석";
  if (parser === "rule") return "서버 연결됨 · 규칙 기반 문장 해석";
  return "서버 연결됨";
}

export function Header({ activeTab, cartCount, server, parser, onRatings, onCart }: Props) {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#0d121c]/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-5 text-sm font-medium">
          <button
            onClick={onRatings}
            className={`flex items-center gap-1.5 transition-colors ${
              activeTab === "ratings" ? "font-bold text-emerald-400" : "text-slate-400 hover:text-white"
            }`}
          >
            <TrendingUp className="h-4 w-4 text-emerald-400" />
            <span>추천 메뉴</span>
            <span className="rounded border border-purple-500/40 bg-purple-900/60 px-1.5 py-0.5 text-[10px] text-purple-300">
              별점 랭킹
            </span>
          </button>
          <button onClick={onCart} className="flex items-center gap-1.5 text-slate-400 transition-colors hover:text-white">
            <ShoppingCart className="h-4 w-4 text-emerald-400" />
            <span>장바구니</span>
            {cartCount > 0 && (
              <span className="rounded-full bg-emerald-400 px-1.5 text-xs font-extrabold text-slate-950">{cartCount}</span>
            )}
          </button>
        </div>

        <div className="hidden items-center gap-2 text-xs text-slate-400 sm:flex" data-testid="server-status">
          <span className="relative flex h-2 w-2">
            {server === "up" && (
              <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75 motion-safe:animate-ping" />
            )}
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                server === "up" ? "bg-emerald-400" : server === "down" ? "bg-rose-400" : "bg-slate-500"
              }`}
            />
          </span>
          <span>{statusText(server, parser)}</span>
        </div>
      </div>
    </header>
  );
}
