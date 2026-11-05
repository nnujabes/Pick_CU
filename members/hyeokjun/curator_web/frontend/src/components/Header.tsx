import { Button } from "@/components/ui/button";
import { useStore } from "@/store/AppStore";

interface Props {
  onAllProducts: () => void;
  onCart: () => void;
  onMyReviews: () => void;
}

export function Header({ onAllProducts, onCart, onMyReviews }: Props) {
  const { cartCount } = useStore();
  return (
    <header className="sticky top-0 z-30 h-16 border-b border-line bg-bg">
      <div className="page-container flex h-full items-center gap-2 min-[521px]:gap-4">
        <p className="flex items-center gap-2 whitespace-nowrap font-mono text-[17px] font-bold">
          <i className="inline-block h-3 w-3 rotate-45 rounded-[2px] bg-lime" aria-hidden data-logo-mark />
          Pick CU
        </p>
        <nav className="flex items-center gap-1 min-[521px]:gap-2" aria-label="주요 메뉴">
          <Button variant="quiet" size="sm" className="px-2" onClick={onAllProducts}>
            전체 상품
          </Button>
          <Button variant="quiet" size="sm" className="px-2" onClick={onCart}>
            장바구니
            {cartCount > 0 && (
              <span className="tnum rounded-chip bg-lime px-2 font-mono text-xs font-bold text-lime-ink" aria-label={`담은 상품 ${cartCount}개`}>
                {cartCount}
              </span>
            )}
          </Button>
        </nav>
        <Button variant="ghost" size="sm" className="ml-auto px-2 min-[521px]:px-3" onClick={onMyReviews} data-header-right>
          내 리뷰
        </Button>
      </div>
    </header>
  );
}
