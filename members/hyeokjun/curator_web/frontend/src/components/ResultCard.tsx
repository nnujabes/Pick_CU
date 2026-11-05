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
  featured: boolean;
  selected: boolean;
  onSelect: (row: ResultRow) => void;
  onAdd: (row: ResultRow) => void;
  onReview: (row: ResultRow) => void;
}

function ItemRating({ product }: { product: Product }) {
  const { rating, count } = useProductStat(product);
  return (
    <span className="tnum absolute bottom-1 left-1 rounded-btn bg-[#1b1c19] px-1 font-mono text-[11px] text-fg" data-rating={product.item_cd}>
      {rating != null ? `★ ${rating.toFixed(1)} (${count})` : "리뷰 없음"}
    </span>
  );
}

function NutritionOverlay({ product }: { product: Product }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex flex-col justify-center bg-[#1b1c19]/95 p-3" role="tooltip">
      <p className="mb-2 truncate text-[13px] font-medium text-fg">{splitBrand(product.product_name).name}</p>
      <table className="tnum w-full font-mono text-xs text-fg">
        <tbody>
          {NUTRIENT_KEYS.map((key) => (
            <tr key={key}>
              <th scope="row" className="py-px text-left font-normal text-muted">{NUTRIENTS[key].ko}</th>
              <td className="py-px text-right">{formatNutrient(key, product[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PhotoArea({ row }: { row: ResultRow }) {
  const [hovered, setHovered] = useState<Product | null>(null);
  const promos = row.items.filter((item) => item.event_type !== "NONE");
  const isCombo = row.items.length > 1;
  return (
    <div className="relative overflow-hidden rounded-t-card bg-white" style={{ aspectRatio: "4 / 3" }} data-photo-area onMouseLeave={() => setHovered(null)}>
      <div className="flex h-full">
        {row.items.map((item, index) => (
          <Fragment key={item.item_cd}>
            {index > 0 && (
              <span className="relative z-[1] -mx-3 flex w-6 flex-none items-center justify-center self-center rounded-chip bg-[#1b1c19] font-mono text-sm font-bold leading-6 text-lime" aria-hidden>
                +
              </span>
            )}
            <div
              className="relative min-w-0 flex-1"
              tabIndex={0}
              aria-label={`${item.product_name} 영양 정보`}
              data-photo-cell
              onMouseEnter={() => setHovered(item)}
              onFocus={() => setHovered(item)}
              onBlur={() => setHovered(null)}
            >
              <ProductImage url={item.image_url} category={item.category} alt={item.product_name} />
              <ItemRating product={item} />
            </div>
          </Fragment>
        ))}
      </div>
      <span className="tnum absolute left-2 top-2 rounded-btn bg-[#1b1c19] px-2 font-mono text-xl font-bold leading-7 text-lime">{row.rank}</span>
      {promos.length > 0 && (
        <span className="absolute right-2 top-2 flex flex-col items-end gap-1">
          {promos.map((item) => (
            <span key={item.item_cd} className="rounded-btn bg-warm px-2 font-mono text-xs font-bold leading-5 text-[#2a1c08]">
              {isCombo ? `${splitBrand(item.product_name).brand ?? ""} ` : ""}{item.event_type}
            </span>
          ))}
        </span>
      )}
      {hovered && <NutritionOverlay product={hovered} />}
    </div>
  );
}

export function ResultCard({ row, parsed, index, featured, selected, onSelect, onAdd, onReview }: Props) {
  const conditions = activeConditions(parsed);
  const conditionKeys = new Set(conditions.map((condition) => condition.key));
  const others = NUTRIENT_KEYS.filter((key) => !conditionKeys.has(key));
  const categories = [...new Set(row.items.map((item) => item.category))];
  const names = row.items.map((item) => splitBrand(item.product_name));
  const brands = [...new Set(names.flatMap((item) => (item.brand ? [item.brand] : [])))];

  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut", delay: index * 0.06 }}
      onClick={() => onSelect(row)}
      onKeyDown={(event) => {
        if (event.key === "Enter" && (event.target as HTMLElement).dataset.photoCell !== undefined) onSelect(row);
      }}
      data-featured={featured}
      className={cn(
        "result-card flex min-w-0 cursor-pointer flex-col overflow-hidden rounded-card border bg-panel transition-colors",
        featured && "result-card-featured",
        selected ? "border-lime" : "border-line hover:border-muted",
      )}
    >
      <PhotoArea row={row} />
      <div className="flex flex-1 flex-col p-4">
        {brands.length > 0 && <p className="truncate font-mono text-xs text-dim">{brands.join(" + ")}</p>}
        <h4 className="line-clamp-2 text-base font-medium leading-snug" title={row.items.map((item) => item.product_name).join(" + ")}>
          {names.map((item) => item.name).join(" + ")}
        </h4>
        <div className="mt-2 flex flex-wrap gap-1 font-mono text-xs">
          {categories.map((category) => (
            <span key={category} className="rounded-btn border border-line px-1 text-muted">
              {category}
            </span>
          ))}
        </div>
        <div className="mt-3 grid gap-2">
          {conditions.map(({ key, direction }) => (
            <NutrientBar key={key} nutrient={key} direction={direction} value={row.totals[key]} />
          ))}
        </div>
        <p className="tnum mt-2 text-[13px] text-muted">
          {others.map((key) => `${NUTRIENTS[key].ko} ${formatNutrient(key, row.totals[key])}`).join(" · ")}
        </p>
        <div className="mt-auto pt-3">
          <p className="tnum flex items-baseline justify-between gap-2">
            <span className="font-mono text-lg font-bold">{formatWon(row.total_price)}</span>
            <span className="font-mono text-xs text-dim">점수 {row.total_score.toFixed(1)}</span>
          </p>
          <div className="mt-2 grid grid-cols-2 gap-2 max-[300px]:grid-cols-1">
            <Button
              variant="lime"
              size="sm"
              className="min-w-0 whitespace-normal px-2"
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
              className="min-w-0 whitespace-normal px-2"
              onClick={(event) => {
                event.stopPropagation();
                onReview(row);
              }}
            >
              이 조합 골랐어요
            </Button>
          </div>
        </div>
      </div>
    </motion.article>
  );
}
