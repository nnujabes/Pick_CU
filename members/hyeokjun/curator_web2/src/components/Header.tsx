import { LayoutGrid, Moon, ShoppingCart, Store, Sun, TrendingUp } from "lucide-react";
import type { Theme } from "@/hooks/useTheme";

export type Tab = "home" | "ratings" | "products";

interface Props {
  activeTab: Tab;
  cartCount: number;
  onHome: () => void;
  onRatings: () => void;
  onCart: () => void;
  onProducts: () => void;
  theme: Theme;
  onToggleTheme: () => void;
}

export function Header({ activeTab, cartCount, onHome, onRatings, onCart, onProducts, theme, onToggleTheme }: Props) {
  const themeLabel = theme === "dark" ? "화이트 모드로 바꾸기" : "다크 모드로 바꾸기";
  return (
    <header className="sticky top-0 z-40 border-b border-panel-line/70 bg-page/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1480px] items-center justify-between gap-2 px-3 sm:px-8">
        <div className="flex h-full items-center gap-2 sm:gap-6">
          <button onClick={onHome} className="flex items-center gap-2.5" aria-label="메인 화면으로">
            <Store className="h-7 w-7 text-cta-fg" strokeWidth={1.75} />
            <span className="hidden whitespace-nowrap text-lg font-extrabold text-strong sm:inline">영양 편의점</span>
          </button>
          <span className="hidden h-4 w-px bg-slate-600 sm:block" aria-hidden />
          <button
            onClick={onRatings}
            aria-current={activeTab === "ratings" ? "page" : undefined}
            className={`relative flex h-full items-center gap-2 px-1 text-sm font-semibold transition-colors ${
              activeTab === "ratings" ? "text-strong" : "text-slate-300 hover:text-strong"
            }`}
          >
            <TrendingUp className="hidden h-5 w-5 text-cta-fg sm:block" />
            <span className="whitespace-nowrap">추천 메뉴</span>
            {activeTab === "ratings" && <span className="absolute inset-x-0 bottom-0 h-[3px] rounded-full bg-cta" />}
          </button>
          <button onClick={onCart} className="flex h-full items-center gap-2 text-sm font-semibold text-slate-300 transition-colors hover:text-strong">
            <ShoppingCart className="hidden h-5 w-5 sm:block" />
            <span className="whitespace-nowrap">장바구니</span>
            {cartCount > 0 && (
              <span className="rounded-full bg-cta px-1.5 text-xs font-extrabold text-cta-ink">{cartCount}</span>
            )}
          </button>
          <button
            onClick={onProducts}
            aria-current={activeTab === "products" ? "page" : undefined}
            className={`relative flex h-full items-center gap-2 px-1 text-sm font-semibold transition-colors ${
              activeTab === "products" ? "text-strong" : "text-slate-300 hover:text-strong"
            }`}
          >
            <LayoutGrid className="hidden h-5 w-5 sm:block" />
            <span className="whitespace-nowrap">전체 상품</span>
            {activeTab === "products" && <span className="absolute inset-x-0 bottom-0 h-[3px] rounded-full bg-cta" />}
          </button>
        </div>

        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={themeLabel}
          title={themeLabel}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-panel-line text-slate-300 transition-colors hover:text-strong"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
}
