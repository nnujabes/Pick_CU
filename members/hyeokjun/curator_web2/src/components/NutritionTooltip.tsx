import type { Product } from "@/api/types";
import { formatNutrient, NUTRIENT_KEYS, NUTRIENTS } from "@/utils/format";

export interface TooltipState {
  product: Product;
  rect: DOMRect;
}

const WIDTH = 240;
const HEIGHT_ESTIMATE = 210;
const GAP = 10;
const SCREEN_MARGIN = 8;
const STICKY_HEADER = 64;

export function NutritionTooltip({ product, rect }: TooltipState) {
  const center = rect.left + rect.width / 2;
  const halfWidth = WIDTH / 2 + SCREEN_MARGIN;
  const left = Math.max(halfWidth, Math.min(window.innerWidth - halfWidth, center));
  // 위쪽에 자리가 없으면 상품 아래에 띄운다.
  const above = rect.top - GAP - HEIGHT_ESTIMATE >= STICKY_HEADER;
  return (
    <div
      role="tooltip"
      style={{
        left,
        top: above ? rect.top - GAP : rect.bottom + GAP,
        width: WIDTH,
        transform: above ? "translate(-50%, -100%)" : "translateX(-50%)",
      }}
      className="pointer-events-none fixed z-50 rounded-xl border-2 border-emerald-400/80 bg-slate-950/95 p-3 text-xs shadow-[0_0_20px_rgba(16,185,129,0.4)] backdrop-blur"
    >
      <div className="mb-2 flex items-center justify-between gap-2 border-b border-slate-800 pb-1.5">
        <span className="truncate font-bold text-white">{product.product_name}</span>
        <span className="shrink-0 rounded bg-emerald-950 px-1.5 text-[10px] font-semibold text-emerald-400">
          {product.category}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-1 text-slate-300">
        {NUTRIENT_KEYS.map((key) => (
          <div key={key} className="flex justify-between rounded bg-slate-900/80 px-2 py-0.5">
            <span className="text-slate-400">{NUTRIENTS[key].ko}</span>
            <span className={key === "protein" ? "font-bold text-emerald-400" : key === "calories" ? "font-bold text-white" : "font-medium"}>
              {formatNutrient(key, product[key])}
            </span>
          </div>
        ))}
      </div>
      {product.event_type !== "NONE" && (
        <p className="mt-2 font-semibold text-purple-300">{product.event_type} 행사 상품</p>
      )}
    </div>
  );
}
