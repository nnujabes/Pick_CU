import { useEffect, useState } from "react";
import { LayoutGrid, Loader2, Search, Star, X } from "lucide-react";
import { fetchProducts } from "@/api/client";
import type { Category, ListedProduct, Product, ProductPromo, ProductSort } from "@/api/types";
import { CATEGORIES, formatNutrient, formatWon } from "@/utils/format";
import { CATEGORY_ICONS } from "./CategoryPicker";
import { ProductImage } from "./ProductImage";

const PAGE_SIZE = 30;

const SORTS: { value: ProductSort; label: string }[] = [
  { value: "default", label: "이름순" },
  { value: "price", label: "낮은 가격순" },
  { value: "protein", label: "단백질 많은 순" },
  { value: "calories", label: "열량 낮은 순" },
  { value: "sugar", label: "당류 적은 순" },
  { value: "sodium", label: "나트륨 적은 순" },
];

const PROMOS: { value: ProductPromo; label: string }[] = [
  { value: "", label: "전체" },
  { value: "1+1", label: "1+1" },
  { value: "2+1", label: "2+1" },
];

type Hover = (event: { currentTarget: HTMLElement }, product: Product) => void;

interface Props {
  onHover: Hover;
  onHoverEnd: () => void;
}

/** 전체 상품 목록. 서버의 GET /products를 그대로 보여 준다. */
export function ProductsPage({ onHover, onHoverEnd }: Props) {
  const [category, setCategory] = useState<Category | "">("");
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<ProductSort>("default");
  const [promo, setPromo] = useState<ProductPromo>("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<ListedProduct[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 조건을 바꾸면 같은 렌더에서 첫 페이지로 돌린다. 그래야 옛 페이지 번호로 새 조건을 받지 않는다.
  const changeFilter = <T,>(set: (value: T) => void) => (value: T) => {
    set(value);
    setPage(1);
  };
  const chooseCategory = changeFilter(setCategory);
  const chooseSort = changeFilter(setSort);
  const choosePromo = changeFilter(setPromo);

  // 검색어는 입력이 멈추고 0.3초 뒤에 반영한다.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = input.trim();
      if (next !== query) {
        setQuery(next);
        setPage(1);
      }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [input, query]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchProducts({ category, q: query, sort, promo, page, size: PAGE_SIZE }, controller.signal)
      .then((data) => {
        setTotal(data.total);
        setItems((previous) => (page === 1 ? data.items : [...previous, ...data.items]));
      })
      .catch((failure: Error) => {
        if (!controller.signal.aborted) setError(failure.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [category, query, sort, promo, page]);

  const hasMore = total !== null && items.length < total;

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3 px-1">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-black text-white">
            <LayoutGrid className="h-6 w-6 text-cta" />
            전체 상품
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            {total === null ? "상품을 불러오는 중이에요." : `조건에 맞는 상품 ${total.toLocaleString("ko-KR")}개`}
            {" · "}사진에 마우스를 올리거나 누르면 6대 영양정보가 표시됩니다
          </p>
        </div>
      </div>

      {/* 카테고리 */}
      <div className="mb-4 flex flex-wrap gap-2">
        {(["", ...CATEGORIES] as (Category | "")[]).map((value) => {
          const active = category === value;
          const Icon = value ? CATEGORY_ICONS[value] : LayoutGrid;
          return (
            <button
              key={value || "all"}
              type="button"
              aria-pressed={active}
              onClick={() => chooseCategory(value)}
              className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-semibold transition-colors ${
                active ? "border-cta bg-cta-soft text-white" : "border-panel-line bg-panel text-slate-300 hover:border-slate-500 hover:text-white"
              }`}
            >
              <Icon className="h-4 w-4" strokeWidth={1.75} />
              {value || "전체"}
            </button>
          );
        })}
      </div>

      {/* 검색 · 행사 · 정렬 */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex flex-1 items-center rounded-xl border border-panel-line bg-panel focus-within:border-cta/70">
          <Search className="absolute left-4 h-5 w-5 text-slate-400" />
          <input
            type="search"
            aria-label="상품 이름 검색"
            placeholder="상품 이름으로 찾기 (예: 닭가슴살)"
            value={input}
            maxLength={50}
            onChange={(event) => setInput(event.target.value)}
            className="w-full bg-transparent py-3 pl-12 pr-10 text-sm text-white placeholder-slate-500 outline-none [&::-webkit-search-cancel-button]:hidden"
          />
          {input && (
            <button
              type="button"
              aria-label="검색어 지우기"
              onClick={() => setInput("")}
              className="absolute right-3 flex h-6 w-6 items-center justify-center rounded-full bg-slate-700/80 text-slate-300 hover:bg-slate-600 hover:text-white"
            >
              <X className="h-3.5 w-3.5 stroke-[2.5]" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-xl border border-panel-line bg-panel p-1" role="group" aria-label="행사">
            {PROMOS.map((item) => (
              <button
                key={item.label}
                type="button"
                aria-pressed={promo === item.value}
                onClick={() => choosePromo(item.value)}
                className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
                  promo === item.value ? "bg-cta text-cta-ink" : "text-slate-300 hover:text-white"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <select
            aria-label="정렬"
            value={sort}
            onChange={(event) => chooseSort(event.target.value as ProductSort)}
            className="rounded-xl border border-panel-line bg-panel px-3 py-2.5 text-sm text-white outline-none focus:border-cta/70"
          >
            {SORTS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error ? (
        <p role="alert" className="rounded-xl border border-rose-500/50 bg-rose-950/40 px-4 py-3 text-sm font-semibold text-rose-200">
          {error}
        </p>
      ) : items.length === 0 && !loading ? (
        <p className="rounded-2xl border border-panel-line bg-panel px-6 py-10 text-center text-slate-300">조건에 맞는 상품이 없어요.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {items.map((product) => (
            <li key={product.item_cd}>
              <button
                type="button"
                aria-label={`${product.product_name} 영양정보`}
                onPointerEnter={(event) => {
                  if (event.pointerType === "mouse") onHover(event, product);
                }}
                onPointerLeave={(event) => {
                  if (event.pointerType === "mouse") onHoverEnd();
                }}
                onClick={(event) => onHover(event, product)}
                onFocus={(event) => onHover(event, product)}
                onBlur={onHoverEnd}
                onKeyDown={(event) => {
                  if (event.key === "Escape") onHoverEnd();
                }}
                className="group flex h-full w-full flex-col overflow-hidden rounded-2xl border border-panel-line bg-panel text-left transition-colors hover:border-cta/70"
              >
                <span className="relative block aspect-square w-full bg-white p-3">
                  <ProductImage url={product.image_url} alt="" />
                  {product.event_type !== "NONE" && (
                    <span className="absolute left-2 top-2 rounded-md bg-violet-600 px-1.5 py-0.5 text-[11px] font-bold text-white">
                      {product.event_type}
                    </span>
                  )}
                </span>
                <span className="flex flex-1 flex-col gap-1 p-3">
                  <span className="text-[11px] text-slate-400">{product.category}</span>
                  <span className="line-clamp-2 text-sm font-semibold text-white">{product.product_name}</span>
                  <span className="mt-auto pt-1 text-base font-extrabold text-white">{formatWon(product.price)}</span>
                  <span className="text-[11px] text-slate-400">
                    단백질 {formatNutrient("protein", product.protein)} · {formatNutrient("calories", product.calories)}
                  </span>
                  {product.n_reviews > 0 && product.avg_rating !== null && (
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-amber-400">
                      <Star className="h-3 w-3 fill-amber-400" />
                      {product.avg_rating.toFixed(1)}
                      <span className="font-normal text-slate-500">({product.n_reviews})</span>
                    </span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6 flex justify-center">
        {loading ? (
          <p className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin text-cta" />
            불러오는 중…
          </p>
        ) : (
          hasMore && (
            <button
              type="button"
              onClick={() => setPage((current) => current + 1)}
              className="rounded-xl border border-panel-line bg-panel px-6 py-2.5 text-sm font-semibold text-slate-200 hover:border-cta/70 hover:text-white"
            >
              더 보기 ({items.length.toLocaleString("ko-KR")} / {total?.toLocaleString("ko-KR")})
            </button>
          )
        )}
      </div>
    </section>
  );
}
