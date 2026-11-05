import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchCategories, postRecommend, postReview } from "@/api/client";
import type { Category, MockCase, Parsed, ProductStat, RecommendResponse, ResultRow, SavedReview } from "@/api/types";
import { AppPanel, SAMPLES } from "@/components/AppPanel";
import { BasketBar } from "@/components/BasketBar";
import { CartPanel } from "@/components/CartPanel";
import type { ChatMessage } from "@/components/ChatLog";
import { Header } from "@/components/Header";
import { MyReviewsPanel } from "@/components/MyReviewsPanel";
import { ResultsPanel, type ResultsState } from "@/components/ResultsPanel";
import { ReviewDialog, type ReviewTarget } from "@/components/ReviewDialog";
import { Scene3D } from "@/components/Scene3D";
import { ShelfDrawer, type ProductPanelState } from "@/components/ShelfDrawer";
import { useReducedMotion } from "@/hooks/useMedia";
import { useStore } from "@/store/AppStore";
import { getSessionId } from "@/utils/storage";

const API_DOWN_MESSAGE = "API 서버에 연결하지 못했어요. 백엔드가 켜져 있는지 확인해 주세요.";

type OpenPanel = "cart" | "reviews" | null;
type NewMessage =
  | { who: "user"; text: string }
  | { who: "bot"; response: RecommendResponse }
  | { who: "error"; text: string };

const rowKey = (row: ResultRow) => row.items.map((item) => item.item_cd).join("-");

export function App() {
  const inputRef = useRef<HTMLInputElement>(null);
  const nextId = useRef(1);
  const reduced = useReducedMotion();
  const { lines, cartCount, addToCart, stats, mergeStats, replaceStats } = useStore();

  const [categories, setCategories] = useState<Category[]>(["식품", "음료"]);
  const [categoryWarning, setCategoryWarning] = useState<string | null>(null);
  const [counts, setCounts] = useState<Partial<Record<Category, number>>>({});
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingText, setPendingText] = useState<string | null>(null);
  const [results, setResults] = useState<ResultsState>({ kind: "first" });
  const [loading, setLoading] = useState(false);
  const [productPanel, setProductPanel] = useState<ProductPanelState>(null);
  const [openPanel, setOpenPanel] = useState<OpenPanel>(null);
  const [selectedRow, setSelectedRow] = useState<ResultRow | null>(null);
  const [reviewTarget, setReviewTarget] = useState<ReviewTarget | null>(null);
  const [reviewsVersion, setReviewsVersion] = useState(0);
  const [lastQuery, setLastQuery] = useState<{ text: string; parsed: Parsed } | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories()
      .then((summary) => setCounts(Object.fromEntries(summary.categories.map((item) => [item.name, item.count]))))
      .catch(() => setResults({ kind: "error", message: API_DOWN_MESSAGE }));
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const focusPrompt = useCallback(() => {
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
    inputRef.current?.focus({ preventScroll: true });
  }, [reduced]);

  // 첫 화면에서 바로 입력할 수 있게 한다. 휴대폰은 키보드가 화면을 가려서 제외한다.
  useEffect(() => {
    if (window.matchMedia("(hover: hover)").matches) inputRef.current?.focus({ preventScroll: true });
  }, []);

  const pinned = useMemo(() => {
    const map: Partial<Record<Category, number>> = {};
    if (results.kind === "response") {
      results.response.results.forEach((row) =>
        row.items.forEach((item) => {
          map[item.category] = (map[item.category] ?? 0) + 1;
        }),
      );
    }
    return map;
  }, [results]);

  const highlighted = useMemo(
    () => (selectedRow ? [...new Set(selectedRow.items.map((item) => item.category))] : []),
    [selectedRow],
  );

  function pushMessage(message: NewMessage) {
    const id = nextId.current++;
    setMessages((current) => [...current, { ...message, id }]);
  }

  async function ask(text: string, options: { asked?: Category[]; useMock?: MockCase; pending?: string | null } = {}) {
    const asked = options.asked ?? categories;
    if (!asked.length) {
      setCategoryWarning("카테고리를 하나 이상 골라 주세요.");
      return;
    }
    setCategoryWarning(null);
    setSelectedRow(null);
    pushMessage({ who: "user", text });
    setLoading(true);
    setResults({ kind: "loading" });
    try {
      const response = await postRecommend(
        { text, categories: asked, pending_text: options.pending ?? null },
        options.useMock,
      );
      pushMessage({ who: "bot", response });
      setPendingText(response.status === "ask" ? text : null);
      setLastQuery({ text: options.pending ? `${options.pending} ${text}` : text, parsed: response.parsed });
      setResults({ kind: "response", id: nextId.current++, response });
    } catch (reason) {
      const message = reason instanceof TypeError ? API_DOWN_MESSAGE : reason instanceof Error ? reason.message : API_DOWN_MESSAGE;
      pushMessage({ who: "error", text: message });
      setResults({ kind: "error", message });
    } finally {
      setLoading(false);
    }
  }

  function changeCategories(next: Category[]) {
    setCategories(next);
    setCategoryWarning(null);
  }

  function runSample(sample: (typeof SAMPLES)[number]) {
    const asked = sample.categories ?? (categories.length ? categories : (["식품", "음료"] as Category[]));
    changeCategories(asked);
    void ask(sample.text, { asked });
  }

  function addWithToast(products: Parameters<typeof addToCart>[0]) {
    addToCart(products);
    setToast("바구니에 담았어요.");
  }

  /** 먼저 화면의 별점을 바꾸고, 서버 응답으로 확정한다. 실패하면 되돌린다. */
  async function saveReview(target: ReviewTarget, rating: number, comment: string) {
    const previous = stats;
    if (target.initialRating == null) {
      const known = new Map<string, { avg: number | null; n: number }>();
      if (results.kind === "response") {
        results.response.results.forEach((row) =>
          row.items.forEach((item) => known.set(item.item_cd, { avg: item.avg_rating ?? null, n: item.n_reviews ?? 0 })),
        );
      }
      lines.forEach((line) =>
        known.set(line.product.item_cd, { avg: line.product.avg_rating ?? null, n: line.product.n_reviews ?? 0 }),
      );
      const optimistic: ProductStat[] = target.barcodes.map((barcode) => {
        const base = stats[barcode]
          ? { avg: stats[barcode].avg_rating, n: stats[barcode].n_reviews }
          : known.get(barcode) ?? { avg: null, n: 0 };
        const total = (base.avg ?? 0) * base.n + rating;
        return { barcode, avg_rating: Math.round((total / (base.n + 1)) * 10) / 10, n_reviews: base.n + 1 };
      });
      mergeStats(optimistic);
    }
    try {
      const saved = await postReview({
        barcodes: target.barcodes,
        rating,
        comment,
        query_text: lastQuery?.text ?? null,
        parsed_json: lastQuery?.parsed ?? null,
        session_id: getSessionId(),
      });
      mergeStats(saved.product_stats);
      setReviewTarget(null);
      setReviewsVersion((current) => current + 1);
      setToast("리뷰가 저장됐어요");
    } catch (reason) {
      replaceStats(previous);
      throw reason;
    }
  }

  function reviewRow(row: ResultRow) {
    setReviewTarget({
      barcodes: row.items.map((item) => item.item_cd),
      names: row.items.map((item) => item.product_name),
    });
  }

  function reviewCart() {
    setOpenPanel(null);
    setReviewTarget({
      barcodes: lines.map((line) => line.product.item_cd),
      names: lines.map((line) => line.product.product_name),
    });
  }

  function editReview(review: SavedReview) {
    setOpenPanel(null);
    setReviewTarget({
      barcodes: review.barcodes,
      names: review.items.map((item) => item.product_name ?? item.barcode),
      initialRating: review.rating,
      initialComment: review.comment ?? "",
    });
  }

  return (
    <>
      <Header
        onAllProducts={() => setProductPanel({ kind: "all" })}
        onCart={() => setOpenPanel("cart")}
        onMyReviews={() => setOpenPanel("reviews")}
      />
      <main className="page-container stage" data-basket={cartCount > 0}>
        <div className="stage-left">
          <AppPanel
            ref={inputRef}
            categories={categories}
            counts={counts}
            categoryWarning={categoryWarning}
            messages={messages}
            loading={loading}
            onCategories={changeCategories}
            onAsk={(text) => void ask(text, { pending: pendingText })}
            onQuickReply={(text) => void ask(text, { pending: pendingText })}
            onSample={runSample}
            onMock={(mock) => void ask(`[mock] ${mock}`, { useMock: mock })}
          />
        </div>
        <div className="stage-right">
          <Scene3D
            selected={categories}
            pinned={pinned}
            focused={productPanel?.kind === "shelf" ? productPanel.category : null}
            highlighted={highlighted}
            counts={counts}
            onOpen={(category) => setProductPanel({ kind: "shelf", category })}
          />
          <ResultsPanel
            state={results}
            selectedKey={selectedRow ? rowKey(selectedRow) : null}
            onSelect={setSelectedRow}
            onAdd={(row) => addWithToast(row.items)}
            onReview={reviewRow}
          />
        </div>
      </main>

      <ShelfDrawer
        state={productPanel}
        onClose={() => setProductPanel(null)}
        onAdd={(product) => addWithToast([product])}
        onRecommend={(category) => {
          changeCategories([category]);
          setProductPanel(null);
          window.setTimeout(focusPrompt, 60);
        }}
      />
      <CartPanel open={openPanel === "cart"} onClose={() => setOpenPanel(null)} onReview={reviewCart} />
      <MyReviewsPanel
        open={openPanel === "reviews"}
        version={reviewsVersion}
        onClose={() => setOpenPanel(null)}
        onEdit={editReview}
      />
      <BasketBar onOpen={() => setOpenPanel("cart")} />
      <ReviewDialog target={reviewTarget} onClose={() => setReviewTarget(null)} onSubmit={saveReview} />

      <AnimatePresence>
        {toast && (
          <motion.div
            role="status"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed bottom-24 left-1/2 z-[60] -translate-x-1/2 whitespace-nowrap rounded-btn bg-fg px-4 py-2 font-mono text-[13px] text-[#1d1e1a]"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
