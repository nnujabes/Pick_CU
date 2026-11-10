import { House, LayoutGrid, Moon, ShoppingCart, Store, Sun, TrendingUp, type LucideIcon } from "lucide-react";
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

interface BottomItem {
  label: string;
  Icon: LucideIcon;
  active: boolean;
  badge: number;
  onClick: () => void;
}

/** 휴대폰 폭의 하단 4분할 메뉴. 헤더의 backdrop-blur 안에서는 fixed가 헤더 기준이 되므로 헤더 밖에 둔다. */
function BottomNav({ items }: { items: BottomItem[] }) {
  return (
    <nav
      aria-label="주요 메뉴"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-panel-line/70 bg-page/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
    >
      {items.map(({ label, Icon, active, badge, onClick }) => (
        <button
          key={label}
          type="button"
          onClick={onClick}
          aria-current={active ? "page" : undefined}
          className={`relative flex h-14 min-w-0 flex-col items-center justify-center gap-0.5 text-xs font-semibold transition-colors ${
            active ? "text-strong" : "text-slate-300"
          }`}
        >
          {active && <span className="absolute inset-x-5 top-0 h-[3px] rounded-full bg-cta" />}
          <span className="relative">
            <Icon className="h-5 w-5" />
            {badge > 0 && (
              <span className="absolute -right-3 -top-1.5 rounded-full bg-cta px-1 text-[10px] font-extrabold text-cta-ink">{badge}</span>
            )}
          </span>
          <span className="whitespace-nowrap">{label}</span>
        </button>
      ))}
    </nav>
  );
}

export function Header({ activeTab, cartCount, onHome, onRatings, onCart, onProducts, theme, onToggleTheme }: Props) {
  const themeLabel = theme === "dark" ? "화이트 모드로 바꾸기" : "다크 모드로 바꾸기";
  return (
    <>
      <header className="sticky top-0 z-40 border-b border-panel-line/70 bg-page/95 backdrop-blur">
        <div className="mx-auto flex h-12 max-w-[1480px] items-center justify-between gap-2 px-4 sm:h-16 sm:px-8">
          <div className="flex h-full items-center gap-6">
            <button onClick={onHome} className="flex items-center gap-2.5" aria-label="메인 화면으로">
              <Store className="hidden h-7 w-7 text-cta-fg sm:block" strokeWidth={1.75} />
              <span className="sign-title whitespace-nowrap text-lg font-black tracking-[0.08em] sm:hidden">영양 편의점</span>
              <span className="hidden whitespace-nowrap text-lg font-extrabold text-strong sm:inline">영양 편의점</span>
            </button>
            <div className="hidden h-full items-center gap-6 sm:flex">
              <span className="h-4 w-px bg-slate-600" aria-hidden />
              <button
                onClick={onRatings}
                aria-current={activeTab === "ratings" ? "page" : undefined}
                className={`relative flex h-full items-center gap-2 px-1 text-sm font-semibold transition-colors ${
                  activeTab === "ratings" ? "text-strong" : "text-slate-300 hover:text-strong"
                }`}
              >
                <TrendingUp className="h-5 w-5 text-cta-fg" />
                <span className="whitespace-nowrap">추천 메뉴</span>
                {activeTab === "ratings" && <span className="absolute inset-x-0 bottom-0 h-[3px] rounded-full bg-cta" />}
              </button>
              <button onClick={onCart} className="flex h-full items-center gap-2 text-sm font-semibold text-slate-300 transition-colors hover:text-strong">
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
                  activeTab === "products" ? "text-strong" : "text-slate-300 hover:text-strong"
                }`}
              >
                <LayoutGrid className="h-5 w-5" />
                <span className="whitespace-nowrap">전체 상품</span>
                {activeTab === "products" && <span className="absolute inset-x-0 bottom-0 h-[3px] rounded-full bg-cta" />}
              </button>
            </div>
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

      <BottomNav
        items={[
          { label: "메인", Icon: House, active: activeTab === "home", badge: 0, onClick: onHome },
          { label: "추천 메뉴", Icon: TrendingUp, active: activeTab === "ratings", badge: 0, onClick: onRatings },
          { label: "장바구니", Icon: ShoppingCart, active: false, badge: cartCount, onClick: onCart },
          { label: "전체 상품", Icon: LayoutGrid, active: activeTab === "products", badge: 0, onClick: onProducts },
        ]}
      />
    </>
  );
}
