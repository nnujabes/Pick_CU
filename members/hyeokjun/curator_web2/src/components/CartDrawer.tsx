import { useEffect, useRef } from "react";
import { ShoppingBag, ShoppingCart, X } from "lucide-react";
import type { Parsed, Product } from "@/api/types";
import { formatNutrient, formatWon } from "@/utils/format";

export interface CartEntry {
  cartId: string;
  title: string;
  items: Product[];
  totalPrice: number;
  protein: number;
  calories: number;
  queryText: string | null;
  parsed: Parsed | null;
}

interface Props {
  items: CartEntry[];
  onClose: () => void;
  onRemove: (cartId: string) => void;
  onClear: () => void;
}

export function CartDrawer({ items, onClose, onRemove, onClear }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const total = items.reduce((sum, item) => sum + item.totalPrice, 0);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      opener?.focus?.();
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-end bg-black/70 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="장바구니"
        className="flex h-full w-full max-w-md flex-col border-l border-slate-800 bg-[#0d121c] p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2">
            <ShoppingCart className="h-5 w-5 text-emerald-400" />
            <h3 className="text-lg font-black text-white">담은 편의점 식단</h3>
            <span className="rounded-full border border-emerald-800 bg-emerald-950 px-2 py-0.5 text-xs font-bold text-emerald-400">
              {items.length}개
            </span>
          </div>
          <button ref={closeRef} onClick={onClose} aria-label="닫기" className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          {items.length === 0 ? (
            <div className="space-y-2 py-16 text-center text-slate-500">
              <ShoppingBag className="mx-auto h-10 w-10 text-slate-600" />
              <p className="text-sm">장바구니가 비어 있습니다.</p>
              <p className="text-xs text-slate-500">추천 결과에서 마음에 드는 식단을 담아보세요.</p>
            </div>
          ) : (
            items.map((entry) => (
              <div key={entry.cartId} className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900 p-3.5">
                <div className="min-w-0">
                  <h4 className="text-sm font-bold text-white">{entry.title}</h4>
                  <p className="mt-0.5 truncate text-[11px] text-slate-400">
                    {entry.items.map((item) => item.product_name).join(" + ")}
                  </p>
                  <p className="mt-0.5 text-xs font-semibold text-emerald-400">
                    단백질 {formatNutrient("protein", entry.protein)} | {formatNutrient("calories", entry.calories)}
                  </p>
                  <span className="text-xs font-bold text-slate-300">{formatWon(entry.totalPrice)}</span>
                </div>
                <button onClick={() => onRemove(entry.cartId)} aria-label={`${entry.title} 삭제`} className="shrink-0 p-1 text-slate-500 hover:text-rose-400">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))
          )}
        </div>

        {items.length > 0 && (
          <div className="space-y-3 border-t border-slate-800 pt-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">합계</span>
              <span className="text-xl font-black text-emerald-400">{formatWon(total)}</span>
            </div>
            <button
              onClick={onClear}
              className="w-full rounded-xl border border-slate-700 bg-slate-800 py-3 text-sm font-bold text-slate-200 hover:bg-slate-700"
            >
              장바구니 비우기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
