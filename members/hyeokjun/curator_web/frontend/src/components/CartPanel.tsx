import { Button } from "@/components/ui/button";
import { useStore } from "@/store/AppStore";
import { formatWon, NUTRIENT_KEYS, splitBrand } from "@/utils/nutrition";
import { NutrientBar } from "./NutrientBar";
import { ProductImage } from "./ProductImage";
import { SidePanel } from "./SidePanel";

interface Props {
  open: boolean;
  onClose: () => void;
  onReview: () => void;
}

export function CartPanel({ open, onClose, onReview }: Props) {
  const { lines, cartCount, setQuantity, removeFromCart } = useStore();
  const sum = (pick: (line: (typeof lines)[number]) => number) => lines.reduce((total, line) => total + pick(line) * line.quantity, 0);

  return (
    <SidePanel open={open} title="장바구니" meta={`${cartCount}개`} onClose={onClose}>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6">
        {!lines.length && <p className="py-6 text-sm text-muted">아직 담은 상품이 없어요.</p>}
        <ul>
          {lines.map((line) => {
            const { product, quantity } = line;
            const { brand, name } = splitBrand(product.product_name);
            return (
              <li key={product.item_cd} className="grid grid-cols-[56px_minmax(0,1fr)] gap-3 border-b border-line py-3">
                <div className="h-14 w-14 overflow-hidden rounded-btn">
                  <ProductImage url={product.image_url} category={product.category} alt={product.product_name} compact />
                </div>
                <div className="min-w-0">
                  {brand && <span className="block font-mono text-xs text-dim">{brand}</span>}
                  <p className="text-[15px] font-medium leading-snug">{name}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Button size="sm" aria-label={`${product.product_name} 하나 빼기`} onClick={() => setQuantity(product.item_cd, quantity - 1)}>−</Button>
                    <span className="tnum min-w-6 text-center font-mono text-sm" aria-label="수량">{quantity}</span>
                    <Button size="sm" aria-label={`${product.product_name} 하나 더`} onClick={() => setQuantity(product.item_cd, quantity + 1)}>+</Button>
                    <Button size="sm" variant="quiet" aria-label={`${product.product_name} 빼기`} onClick={() => removeFromCart(product.item_cd)}>빼기</Button>
                    <span className="tnum ml-auto whitespace-nowrap font-mono text-sm font-bold">{formatWon(product.price * quantity)}</span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
        {lines.length > 0 && (
          <div className="grid gap-2 py-4">
            <p className="font-mono text-xs tracking-[0.06em] text-muted">1일 기준치 대비</p>
            {NUTRIENT_KEYS.map((key) => (
              <NutrientBar key={key} nutrient={key} value={sum((line) => line.product[key])} />
            ))}
          </div>
        )}
      </div>
      <div className="grid gap-3 border-t border-line p-6">
        <p className="flex items-baseline justify-between font-mono text-sm text-muted">
          합계
          <b className="tnum text-lg text-fg">{formatWon(sum((line) => line.product.price))}</b>
        </p>
        <Button variant="lime" disabled={!lines.length} onClick={onReview}>
          이 구성 리뷰 남기기
        </Button>
      </div>
    </SidePanel>
  );
}
