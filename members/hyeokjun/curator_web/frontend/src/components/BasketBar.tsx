import { Button } from "@/components/ui/button";
import { useStore } from "@/store/AppStore";
import { formatNumber, formatWon } from "@/utils/nutrition";

export function BasketBar({ onOpen }: { onOpen: () => void }) {
  const { lines, cartCount, clearCart } = useStore();
  if (!lines.length) return null;

  const sum = (key: "price" | "calories" | "protein" | "sodium" | "sugar") =>
    lines.reduce((total, line) => total + line.product[key] * line.quantity, 0);

  return (
    <aside aria-label="바구니" className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-panel">
      <div className="page-container flex flex-wrap items-center gap-x-4 gap-y-2 py-2">
        <p className="tnum min-w-0 flex-1 basis-[280px] font-mono text-[13px] text-muted">
          바구니 <b className="text-fg">{cartCount}</b>개 · <b className="text-fg">{formatWon(sum("price"))}</b>
          {" · "}열량 {formatNumber(sum("calories"))}kcal · 단백질 {formatNumber(sum("protein"))}g · 나트륨{" "}
          {formatNumber(sum("sodium"))}mg · 당류 {formatNumber(sum("sugar"))}g
        </p>
        <div className="flex gap-2">
          <Button size="sm" onClick={onOpen}>
            자세히
          </Button>
          <Button size="sm" variant="quiet" onClick={clearCart}>
            비우기
          </Button>
        </div>
      </div>
    </aside>
  );
}
