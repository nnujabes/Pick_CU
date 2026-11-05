import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Product, ProductStat } from "@/api/types";
import { readStorage, writeStorage } from "@/utils/storage";

const CART_KEY = "pickcu.cart";

export interface CartLine {
  product: Product;
  quantity: number;
}

interface Store {
  lines: CartLine[];
  cartCount: number;
  addToCart: (products: Product[]) => void;
  setQuantity: (barcode: string, quantity: number) => void;
  removeFromCart: (barcode: string) => void;
  clearCart: () => void;
  /** 저장한 리뷰로 바뀐 별점. 서버 값보다 먼저 쓴다. */
  stats: Record<string, ProductStat>;
  mergeStats: (next: ProductStat[]) => void;
  replaceStats: (next: Record<string, ProductStat>) => void;
}

const StoreContext = createContext<Store | null>(null);

function loadCart(): CartLine[] {
  const raw = readStorage(CART_KEY);
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (line): line is CartLine =>
        typeof line?.product?.item_cd === "string" && typeof line?.quantity === "number" && line.quantity > 0,
    );
  } catch {
    return [];
  }
}

export function AppStoreProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(loadCart);
  const [stats, setStats] = useState<Record<string, ProductStat>>({});

  useEffect(() => writeStorage(CART_KEY, JSON.stringify(lines)), [lines]);

  const addToCart = useCallback((products: Product[]) => {
    setLines((current) => {
      const next = [...current];
      for (const product of products) {
        const index = next.findIndex((line) => line.product.item_cd === product.item_cd);
        if (index >= 0) next[index] = { ...next[index], quantity: next[index].quantity + 1 };
        else next.push({ product, quantity: 1 });
      }
      return next;
    });
  }, []);

  const setQuantity = useCallback((barcode: string, quantity: number) => {
    setLines((current) =>
      quantity <= 0
        ? current.filter((line) => line.product.item_cd !== barcode)
        : current.map((line) => (line.product.item_cd === barcode ? { ...line, quantity } : line)),
    );
  }, []);

  const removeFromCart = useCallback((barcode: string) => {
    setLines((current) => current.filter((line) => line.product.item_cd !== barcode));
  }, []);

  const clearCart = useCallback(() => setLines([]), []);

  const mergeStats = useCallback((next: ProductStat[]) => {
    setStats((current) => ({ ...current, ...Object.fromEntries(next.map((stat) => [stat.barcode, stat])) }));
  }, []);

  const value = useMemo<Store>(() => ({
    lines,
    cartCount: lines.reduce((total, line) => total + line.quantity, 0),
    addToCart,
    setQuantity,
    removeFromCart,
    clearCart,
    stats,
    mergeStats,
    replaceStats: setStats,
  }), [lines, addToCart, setQuantity, removeFromCart, clearCart, stats, mergeStats]);

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const store = useContext(StoreContext);
  if (!store) throw new Error("AppStoreProvider 안에서 써야 합니다.");
  return store;
}

/** 상품의 현재 별점. 방금 쓴 리뷰가 있으면 그 값을 쓴다. */
export function useProductStat(product: Pick<Product, "item_cd" | "avg_rating" | "n_reviews">) {
  const { stats } = useStore();
  const override = stats[product.item_cd];
  return {
    rating: override ? override.avg_rating : product.avg_rating ?? null,
    count: override ? override.n_reviews : product.n_reviews ?? 0,
  };
}
