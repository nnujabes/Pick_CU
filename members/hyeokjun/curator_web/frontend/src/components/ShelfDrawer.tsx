import { useEffect, useRef, useState } from "react";
import { fetchProducts, fetchReviews } from "@/api/client";
import type { Category, Product, PromoKey, SavedReview, SortKey } from "@/api/types";
import { Button } from "@/components/ui/button";
import { useProductStat } from "@/store/AppStore";
import { cn } from "@/utils/cn";
import { CATEGORIES, formatNumber, formatWon, splitBrand } from "@/utils/nutrition";
import { ProductImage } from "./ProductImage";
import { SidePanel } from "./SidePanel";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "default", label: "기본" },
  { key: "price", label: "가격↑" },
  { key: "protein", label: "단백질↑" },
  { key: "sugar", label: "당류↓" },
  { key: "calories", label: "열량↓" },
  { key: "sodium", label: "나트륨↓" },
];
const PROMOS: { key: PromoKey; label: string }[] = [
  { key: "", label: "행사 전체" },
  { key: "1+1", label: "1+1" },
  { key: "2+1", label: "2+1" },
];
const PAGE_SIZE = 20;

/** 전체 상품은 탭이 있고, 진열대는 카테고리가 정해져 있다. */
export type ProductPanelState = { kind: "all" } | { kind: "shelf"; category: Category } | null;

interface Props {
  state: ProductPanelState;
  onClose: () => void;
  onAdd: (product: Product) => void;
  onRecommend: (category: Category) => void;
}

function ChoiceButton({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-btn border px-2 py-1 font-mono text-xs transition-colors",
        active ? "border-lime text-lime" : "border-line text-muted hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

function RecentReviews({ barcode }: { barcode: string }) {
  const [reviews, setReviews] = useState<SavedReview[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchReviews({ barcode, limit: 3 }, controller.signal)
      .then((body) => setReviews(body.items))
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [barcode]);

  if (failed) return <p className="text-[13px] text-alert">리뷰를 불러오지 못했어요.</p>;
  if (!reviews) return <p className="font-mono text-xs text-muted">불러오는 중이에요…</p>;
  if (!reviews.length) return <p className="text-[13px] text-muted">아직 리뷰가 없어요.</p>;
  return (
    <ul className="grid gap-2">
      {reviews.map((review) => (
        <li key={review.id} className="text-[13px]">
          <span className="tnum mr-2 font-mono text-lime">★ {review.rating}</span>
          <span className="text-fg">{review.comment || "한 줄 리뷰 없음"}</span>
        </li>
      ))}
    </ul>
  );
}

function ProductRow({ product, expanded, onToggle, onAdd }: {
  product: Product;
  expanded: boolean;
  onToggle: () => void;
  onAdd: (product: Product) => void;
}) {
  const { brand, name } = splitBrand(product.product_name);
  const { rating, count } = useProductStat(product);
  return (
    <li className="border-b border-line py-3">
      <div className="grid grid-cols-[64px_minmax(0,1fr)_auto] gap-3">
        <div className="h-16 w-16 overflow-hidden rounded-btn">
          <ProductImage url={product.image_url} category={product.category} alt={product.product_name} compact />
        </div>
        <button type="button" onClick={onToggle} aria-expanded={expanded} className="min-w-0 text-left">
          {brand && <span className="block font-mono text-xs text-dim">{brand}</span>}
          <span className="text-[15px] font-medium leading-snug">{name}</span>
          {product.event_type !== "NONE" && (
            <span className="ml-2 whitespace-nowrap rounded-btn border border-[#5a4a33] px-1 font-mono text-xs font-normal text-warm">
              {product.event_type}
            </span>
          )}
          <span className="tnum mt-1 block font-mono text-xs leading-relaxed text-muted">
            열량 {formatNumber(product.calories)}kcal · 단백질 {formatNumber(product.protein)}g · 나트륨 {formatNumber(product.sodium)}mg
            <br />
            탄수화물 {formatNumber(product.carbs)}g · 당류 {formatNumber(product.sugar)}g · 지방 {formatNumber(product.fat)}g
          </span>
          <span className="tnum mt-1 block font-mono text-xs text-dim">
            {rating != null ? `★ ${rating.toFixed(1)} (${count})` : "리뷰 없음"}
          </span>
        </button>
        <div className="flex flex-col items-end gap-2">
          <span className="tnum whitespace-nowrap font-mono text-[15px] font-bold">{formatWon(product.price)}</span>
          <Button size="sm" variant="ghost" aria-label={`${product.product_name} 담기`} onClick={() => onAdd(product)}>
            담기
          </Button>
        </div>
      </div>
      {expanded && (
        <div className="mt-3 rounded-btn border border-line bg-panel-2 p-3">
          <p className="mb-2 font-mono text-xs tracking-[0.06em] text-muted">최근 리뷰</p>
          <RecentReviews barcode={product.item_cd} />
        </div>
      )}
    </li>
  );
}

function ProductList({ fixedCategory, onAdd, onRecommend, onTotal }: {
  fixedCategory: Category | null;
  onAdd: (product: Product) => void;
  onRecommend: (category: Category) => void;
  onTotal: (total: number) => void;
}) {
  const [tab, setTab] = useState<Category | "">("");
  const category = fixedCategory ?? tab;
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("default");
  const [promo, setPromo] = useState<PromoKey>("");
  const [items, setItems] = useState<Product[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 200);
    return () => window.clearTimeout(timer);
  }, [search]);

  // 조건이 바뀌면 처음부터 다시 불러온다.
  useEffect(() => {
    setItems([]);
    setPage(1);
    setTotal(null);
    setExpanded(null);
    listRef.current?.scrollTo({ top: 0 });
  }, [category, query, sort, promo]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchProducts({ category, q: query, sort, promo, page, size: PAGE_SIZE }, controller.signal)
      .then((body) => {
        setTotal(body.total);
        onTotal(body.total);
        setItems((current) => {
          if (page === 1) return body.items;
          const seen = new Set(current.map((item) => item.item_cd));
          return [...current, ...body.items.filter((item) => !seen.has(item.item_cd))];
        });
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "상품을 불러오지 못했어요.");
        setLoading(false);
      });
    return () => controller.abort();
  }, [category, query, sort, promo, page, onTotal]);

  const hasMore = total != null && items.length < total;
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || loading) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) setPage((current) => current + 1);
      },
      { root: listRef.current, rootMargin: "120px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loading, items.length]);

  return (
    <>
      <div className="grid gap-3 border-b border-line p-6">
        {!fixedCategory && (
          <div className="flex flex-wrap gap-1" role="group" aria-label="카테고리">
            <ChoiceButton active={tab === ""} onClick={() => setTab("")}>전체</ChoiceButton>
            {CATEGORIES.map((item) => (
              <ChoiceButton key={item} active={tab === item} onClick={() => setTab(item)}>{item}</ChoiceButton>
            ))}
          </div>
        )}
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="상품명 검색"
          aria-label="상품명 검색"
          className="w-full rounded-btn border border-line bg-panel-2 px-3 py-2 text-base outline-none focus:border-lime"
        />
        <div className="flex flex-wrap gap-1" role="group" aria-label="정렬">
          {SORTS.map((option) => (
            <ChoiceButton key={option.key} active={sort === option.key} onClick={() => setSort(option.key)}>{option.label}</ChoiceButton>
          ))}
        </div>
        <div className="flex flex-wrap gap-1" role="group" aria-label="행사">
          {PROMOS.map((option) => (
            <ChoiceButton key={option.label} active={promo === option.key} onClick={() => setPromo(option.key)}>{option.label}</ChoiceButton>
          ))}
        </div>
      </div>
      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6">
        <ul>
          {items.map((product) => (
            <ProductRow
              key={product.item_cd}
              product={product}
              expanded={expanded === product.item_cd}
              onToggle={() => setExpanded(expanded === product.item_cd ? null : product.item_cd)}
              onAdd={onAdd}
            />
          ))}
        </ul>
        {error && <p role="alert" className="py-4 text-sm text-alert">{error}</p>}
        {!error && total === 0 && <p className="py-6 text-sm text-muted">조건에 맞는 상품이 없어요.</p>}
        {loading && <p className="py-4 font-mono text-[13px] text-muted">불러오는 중이에요…</p>}
        <div ref={sentinelRef} className="h-px" />
      </div>
      {fixedCategory && (
        <div className="border-t border-line p-6">
          <Button variant="lime" className="w-full" onClick={() => onRecommend(fixedCategory)}>
            이 카테고리로 추천 받기
          </Button>
        </div>
      )}
    </>
  );
}

export function ShelfDrawer({ state, onClose, onAdd, onRecommend }: Props) {
  const [total, setTotal] = useState<number | null>(null);
  const title = state?.kind === "shelf" ? state.category : "전체 상품";
  const listKey = state?.kind === "shelf" ? state.category : "all";
  return (
    <SidePanel
      open={Boolean(state)}
      title={title}
      meta={total != null ? `${total.toLocaleString("ko-KR")}개` : undefined}
      onClose={onClose}
    >
      <ProductList
        key={listKey}
        fixedCategory={state?.kind === "shelf" ? state.category : null}
        onAdd={onAdd}
        onRecommend={onRecommend}
        onTotal={setTotal}
      />
    </SidePanel>
  );
}
