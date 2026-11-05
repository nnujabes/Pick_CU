import { motion } from "framer-motion";
import { Fragment, useState } from "react";
import type { Parsed, Product, ResultRow } from "@/api/types";
import { Button } from "@/components/ui/button";
import { useProductStat } from "@/store/AppStore";
import { cn } from "@/utils/cn";
import { activeConditions, formatNutrient, formatWon, NUTRIENT_KEYS, NUTRIENTS, splitBrand } from "@/utils/nutrition";
import { NutrientBar } from "./NutrientBar";
import { ProductImage } from "./ProductImage";

interface Props {
  row: ResultRow;
  parsed: Parsed;
  index: number;
  selected: boolean;
  onSelect: (row: ResultRow) => void;
  onAdd: (row: ResultRow) => void;
  onReview: (row: ResultRow) => void;
}

function ItemRating({ product }: { product: Product }) {
  const { rating, count } = useProductStat(product);
  if (rating == null) return null;
  return (
    <span className="tnum absolute bottom-1 left-1 rounded-btn bg-[#1b1c19] px-1 font-mono text-[11px] text-fg" data-rating={product.item_cd}>
      ★ {rating.toFixed(1)} ({count})
    </span>
  );
}

function NutritionOverlay({ product }: { product: Product }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex flex-col justify-center bg-[#1b1c19]/95 px-2" role="tooltip">
      <table className="tnum w-full font-mono text-[11px] leading-4 text-fg">
        <tbody>
          {NUTRIENT_KEYS.map((key) => (
            <tr key={key}>
              <th scope="row" className="text-left font-normal text-soft">{NUTRIENTS[key].ko}</th>
              <td className="text-right">{formatNutrient(key, product[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PhotoArea({ row }: { row: ResultRow }) {
  const [hovered, setHovered] = useState<Product | null>(null);
  return (
    <div className="relative min-h-0 overflow-hidden bg-white max-[640px]:min-h-28" data-photo-area onMouseLeave={() => setHovered(null)}>
      <div className="absolute inset-0 flex">
        {row.items.map((item, index) => (
          <Fragment key={item.item_cd}>
            {index > 0 && (
              <span className="relative z-[1] -mx-2 flex h-4 w-4 flex-none items-center justify-center self-center rounded-chip bg-[#1b1c19] font-mono text-xs font-bold text-lime" aria-hidden>
                +
              </span>
            )}
            <div
              className="relative min-w-0 flex-1"
              tabIndex={0}
              aria-label={`${item.product_name} 영양 정보`}
              data-photo-cell
              onMouseEnter={() => {
                // 터치 기기에서는 스크롤 뒤 손가락 위치만으로 표가 뜨지 않게 하고, 탭해서 포커스될 때만 보여 준다.
                if (window.matchMedia("(hover: hover)").matches) setHovered(item);
              }}
              onFocus={() => setHovered(item)}
              onBlur={() => setHovered(null)}
            >
              <ProductImage url={item.image_url} category={item.category} alt={item.product_name} className="absolute inset-0" />
              {item.event_type !== "NONE" && (
                <span className="absolute right-1 top-1 rounded-btn bg-warm px-1 font-mono text-[11px] font-bold leading-4 text-[#2a1c08]">
                  {item.event_type}
                </span>
              )}
              <ItemRating product={item} />
            </div>
          </Fragment>
        ))}
      </div>
      <span className="tnum absolute left-1 top-1 rounded-btn bg-[#1b1c19] px-2 font-mono text-base font-bold leading-6 text-lime">{row.rank}</span>
      {hovered && <NutritionOverlay product={hovered} />}
    </div>
  );
}

export function ResultCard({ row, parsed, index, selected, onSelect, onAdd, onReview }: Props) {
  const conditions = activeConditions(parsed);
  const conditionKeys = new Set(conditions.map((condition) => condition.key));
  const others = NUTRIENT_KEYS.filter((key) => !conditionKeys.has(key));
  const categories = [...new Set(row.items.map((item) => item.category))];
  const names = row.items.map((item) => splitBrand(item.product_name));
  const brands = [...new Set(names.flatMap((item) => (item.brand ? [item.brand] : [])))];
  // 상품 3개 조합은 사진 칸을 넓히고, 이름이 모두 보이도록 두 줄을 쓴다.
  const isTriple = row.items.length >= 3;

  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut", delay: index * 0.06 }}
      onClick={() => onSelect(row)}
      onKeyDown={(event) => {
        if (event.key === "Enter" && (event.target as HTMLElement).dataset.photoCell !== undefined) onSelect(row);
      }}
      data-triple={isTriple}
      className={cn(
        "grid min-w-0 cursor-pointer overflow-hidden rounded-card border bg-panel transition-colors",
        isTriple
          ? "grid-cols-[minmax(180px,30%)_minmax(0,1fr)_144px] max-[640px]:grid-cols-1"
          : "grid-cols-[minmax(132px,26%)_minmax(0,1fr)_144px] max-[640px]:grid-cols-[112px_minmax(0,1fr)]",
        selected ? "border-lime" : "border-line hover:border-muted",
      )}
    >
      <PhotoArea row={row} />
      <div className="flex min-w-0 flex-col justify-center gap-1 px-3 py-2">
        {!isTriple && (
          <p className="flex min-w-0 items-center gap-2 font-mono text-xs leading-4">
            {brands.length > 0 && <span className="min-w-0 truncate text-soft">{brands.join(" + ")}</span>}
            {categories.map((category) => (
              <span key={category} className="flex-none text-soft">{category}</span>
            ))}
          </p>
        )}
        <h4
          className={cn(
            "font-medium leading-snug text-fg",
            isTriple ? "line-clamp-2 text-sm" : "truncate text-[15px] max-[640px]:line-clamp-2 max-[640px]:whitespace-normal",
          )}
          title={row.items.map((item) => item.product_name).join(" + ")}
        >
          {names.map((item) => item.name).join(" + ")}
        </h4>
        <div className="grid gap-1">
          {conditions.map(({ key, direction }) => (
            <NutrientBar key={key} nutrient={key} direction={direction} value={row.totals[key]} />
          ))}
        </div>
        <p className="result-others tnum truncate text-xs leading-4 text-soft">
          {others.map((key) => `${NUTRIENTS[key].ko} ${formatNutrient(key, row.totals[key])}`).join(" · ")}
        </p>
      </div>
      <div className="col-span-1 flex min-w-0 flex-col justify-center gap-1 border-l border-line p-2 max-[640px]:col-span-full max-[640px]:flex-row max-[640px]:flex-wrap max-[640px]:items-center max-[640px]:border-l-0 max-[640px]:border-t">
        <p className="tnum flex items-baseline justify-between gap-2 max-[640px]:mr-auto">
          <span className="font-mono text-base font-bold text-fg">{formatWon(row.total_price)}</span>
          <span className="font-mono text-[11px] text-soft" data-score>점수 {row.total_score.toFixed(1)}</span>
        </p>
        <Button
          variant="lime"
          size="sm"
          className="px-1 py-1 text-xs"
          onClick={(event) => {
            event.stopPropagation();
            onAdd(row);
          }}
        >
          바구니에 담기
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="px-1 py-1 text-xs"
          onClick={(event) => {
            event.stopPropagation();
            onReview(row);
          }}
        >
          이 조합 골랐어요
        </Button>
      </div>
    </motion.article>
  );
}
