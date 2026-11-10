import { useCallback, useEffect, useRef, useState } from "react";
import { Check } from "lucide-react";
import { postRecommend } from "@/api/client";
import type { Category, Product, RecommendResponse, ResultRow } from "@/api/types";
import { CartDrawer, type CartEntry } from "@/components/CartDrawer";
import { CategoryPicker } from "@/components/CategoryPicker";
import { Header, type Tab } from "@/components/Header";
import { NutritionTooltip, type TooltipState } from "@/components/NutritionTooltip";
import { ProductsPage } from "@/components/ProductsPage";
import { PromptForm, type InputNotice } from "@/components/PromptForm";
import { RatingsPage, type ReviewTarget } from "@/components/RatingsPage";
import { Results } from "@/components/Results";
import { Signboard } from "@/components/Signboard";
import { useTheme } from "@/hooks/useTheme";
import { comboKey, comboTitle, formatWon, shortName } from "@/utils/format";
import { noticeFor } from "@/utils/notices";
import { defaultPrompt } from "@/utils/prompt";
import { readList, writeList } from "@/utils/storage";

const CART_KEY = "pickcu2.cart";
const INITIAL_CATEGORIES: Category[] = ["간편식사", "음료"];

/** 조합 이름은 서로 겹칠 수 있어 평가 목록에는 상품 이름을 쓴다. */
const targetLabel = (items: Product[], price: number) =>
  `${items.map((item) => shortName(item.product_name)).join(" + ")} (${formatWon(price)})`;

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<Tab>("home");
  const [selectedCategories, setSelectedCategories] = useState<Category[]>(INITIAL_CATEGORIES);
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [pendingText, setPendingText] = useState<string | null>(null);
  const [response, setResponse] = useState<RecommendResponse | null>(null);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [inputNotice, setInputNotice] = useState<InputNotice | null>(null);
  const [cartItems, setCartItems] = useState<CartEntry[]>(() => readList<CartEntry>(CART_KEY));
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [notification, setNotification] = useState("");
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const noticeTimer = useRef<number>();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => writeList(CART_KEY, cartItems), [cartItems]);

  // 스크롤하면 말풍선이 상품에서 떨어져 보이므로 닫는다.
  useEffect(() => {
    if (!tooltip) return;
    const close = () => setTooltip(null);
    window.addEventListener("scroll", close, { capture: true, passive: true });
    return () => window.removeEventListener("scroll", close, { capture: true });
  }, [tooltip]);

  const showNotice = useCallback((message: string) => {
    window.clearTimeout(noticeTimer.current);
    setNotification(message);
    noticeTimer.current = window.setTimeout(() => setNotification(""), 2800);
  }, []);

  const toggleCategory = (category: Category) => {
    if (selectedCategories.includes(category)) {
      if (selectedCategories.length <= 1) return showNotice("최소 1개의 카테고리는 선택되어 있어야 합니다.");
      setSelectedCategories(selectedCategories.filter((item) => item !== category));
    } else {
      if (selectedCategories.length >= 3) return showNotice("카테고리는 최대 3개까지만 선택 가능합니다.");
      setSelectedCategories([...selectedCategories, category]);
    }
  };

  const recommend = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    const pending = pendingText;
    const fullText = pending ? `${pending} ${trimmed}` : trimmed;
    setLoading(true);
    setInputNotice(null);
    setTooltip(null);
    try {
      const next = await postRecommend({ text: trimmed, categories: selectedCategories, pending_text: pending });
      const notice = noticeFor(next);
      if (notice) {
        // 이전 추천을 지우고, 쓴 문장은 고쳐 쓸 수 있게 입력창에 남긴다.
        setResponse(null);
        setPendingText(null);
        setPrompt(fullText);
        setInputNotice(notice);
        inputRef.current?.focus();
        return;
      }
      setResponse(next);
      setLastQuery(fullText);
      if (next.status === "ask") {
        setPendingText(fullText);
        setPrompt("");
        inputRef.current?.focus();
      } else {
        setPendingText(null);
        setPrompt(fullText);
      }
    } catch (failure) {
      setResponse(null);
      setInputNotice({ tone: "error", text: failure instanceof Error ? failure.message : "추천을 불러오지 못했어요." });
    } finally {
      setLoading(false);
    }
  };

  /** 간판이나 [메인 추천으로 돌아가기]를 누르면 처음 화면으로 되돌린다. 장바구니는 남긴다. */
  const goHome = () => {
    if (loading) return;
    setActiveTab("home");
    setSelectedCategories(INITIAL_CATEGORIES);
    setPrompt(defaultPrompt());
    setPendingText(null);
    setResponse(null);
    setLastQuery(null);
    setInputNotice(null);
    setTooltip(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cancelQuestion = () => {
    setPrompt(pendingText ?? "");
    setPendingText(null);
    setResponse(null);
    inputRef.current?.focus();
  };

  const addToCart = (row: ResultRow) => {
    const title = comboTitle(row);
    setCartItems((previous) => [
      ...previous,
      {
        cartId: `${Date.now()}-${Math.random()}`,
        title,
        items: row.items,
        totalPrice: row.total_price,
        protein: row.totals.protein,
        calories: row.totals.calories,
        queryText: lastQuery,
        parsed: response?.parsed ?? null,
      },
    ]);
    showNotice(`'${title}'이(가) 장바구니에 담겼습니다!`);
  };

  /** 전체 상품에서 고른 상품 하나를 담는다. 추천 문장이 없으므로 queryText·parsed는 비운다. */
  const addProductToCart = (product: Product) => {
    const title = shortName(product.product_name);
    setCartItems((previous) => [
      ...previous,
      {
        cartId: `${Date.now()}-${Math.random()}`,
        title,
        items: [product],
        totalPrice: product.price,
        protein: product.protein,
        calories: product.calories,
        queryText: null,
        parsed: null,
      },
    ]);
    showNotice(`'${title}'이(가) 장바구니에 담겼습니다!`);
  };

  const handleHover =(event: { currentTarget: HTMLElement }, product: Product) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltip({ product, rect });
  };

  const reviewTargets: ReviewTarget[] = [];
  const addTarget = (target: ReviewTarget) => {
    if (!reviewTargets.some((item) => item.key === target.key)) reviewTargets.push(target);
  };
  response?.results?.forEach((row) =>
    addTarget({
      key: comboKey(row.items),
      label: targetLabel(row.items, row.total_price),
      barcodes: row.items.map((item) => item.item_cd),
      queryText: lastQuery,
      parsed: response.parsed,
    }),
  );
  cartItems.forEach((entry) =>
    addTarget({
      key: comboKey(entry.items),
      label: targetLabel(entry.items, entry.totalPrice),
      barcodes: entry.items.map((item) => item.item_cd),
      queryText: entry.queryText,
      parsed: entry.parsed,
    }),
  );

  return (
    <div className="min-h-screen bg-page font-sans text-slate-100 selection:bg-cta selection:text-cta-ink">
      <div role="status" aria-live="polite">
        {notification && (
          <div className="fixed left-1/2 top-5 z-[60] flex w-max max-w-[calc(100vw-32px)] -translate-x-1/2 items-center gap-2 rounded-full border border-emerald-300 bg-emerald-500 px-6 py-2.5 font-bold text-on-accent shadow-[0_0_25px_rgb(var(--glow-1)/0.5)]">
            <Check className="h-5 w-5 shrink-0 stroke-[2.5]" />
            <span>{notification}</span>
          </div>
        )}
      </div>

      <Header
        activeTab={activeTab}
        cartCount={cartItems.length}
        onHome={goHome}
        onRatings={() => setActiveTab("ratings")}
        onCart={() => setIsCartOpen(true)}
        onProducts={() => {
          setTooltip(null);
          setActiveTab("products");
        }}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <Signboard onHome={goHome} />

      <main className="mx-auto max-w-[1232px] px-4 pb-24 pt-6 sm:py-10">
        {activeTab === "home" ? (
          <>
            <CategoryPicker selected={selectedCategories} onToggle={toggleCategory} />
            <PromptForm
              value={prompt}
              answering={pendingText !== null}
              loading={loading}
              notice={inputNotice}
              inputRef={inputRef}
              onChange={setPrompt}
              onSubmit={() => recommend(prompt)}
            />
            <Results
              response={response}
              loading={loading}
              onQuickReply={recommend}
              onCancelQuestion={cancelQuestion}
              onAddToCart={addToCart}
              onHover={handleHover}
              onHoverEnd={() => setTooltip(null)}
            />
          </>
        ) : activeTab === "products" ? (
          <ProductsPage onHover={handleHover} onHoverEnd={() => setTooltip(null)} onAddToCart={addProductToCart} />
        ) : (
          <RatingsPage targets={reviewTargets} onHome={goHome} onNotice={showNotice} />
        )}
      </main>

      {tooltip && <NutritionTooltip {...tooltip} />}

      {isCartOpen && (
        <CartDrawer
          items={cartItems}
          onClose={() => setIsCartOpen(false)}
          onRemove={(cartId) => setCartItems((previous) => previous.filter((item) => item.cartId !== cartId))}
          onClear={() => setCartItems([])}
        />
      )}
    </div>
  );
}
