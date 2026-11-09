import { Fragment } from "react";
import { Flame, HelpCircle, Info, Loader2, SearchX, ShoppingCart, Sparkles } from "lucide-react";
import type { Parsed, Product, RecommendResponse, ResultRow } from "@/api/types";
import { useLoadingMessage } from "@/hooks/useLoadingMessage";
import { activeNutrients, comboTitle, conditionText, formatNutrient, formatWon, NUTRIENTS } from "@/utils/format";
import { ProductImage } from "./ProductImage";

type Hover = (event: { currentTarget: HTMLElement }, product: Product) => void;

interface Props {
  response: RecommendResponse | null;
  loading: boolean;
  onQuickReply: (text: string) => void;
  onCancelQuestion: () => void;
  onAddToCart: (row: ResultRow) => void;
  onHover: Hover;
  onHoverEnd: () => void;
}

function Message({ icon, children }: { icon: JSX.Element; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-panel-line bg-panel px-6 py-10 text-center text-base text-slate-200 sm:text-lg">
      <div className="mb-3 flex justify-center text-cta-fg">{icon}</div>
      {children}
    </div>
  );
}

function Notice({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

function ComboCard({ row, parsed, goal, onAddToCart, onHover, onHoverEnd }: {
  row: ResultRow;
  parsed: Parsed;
  goal: string | null;
  onAddToCart: Props["onAddToCart"];
  onHover: Hover;
  onHoverEnd: () => void;
}) {
  const isFirst = row.rank === 1;
  const tagline = [goal && `${goal} 목표`, conditionText(parsed)].filter(Boolean).join(" · ");
  // 단백질·열량은 항상, 사용자가 요청한 영양소는 더해서 보여 준다.
  const extra = activeNutrients(parsed).filter((key) => key !== "protein" && key !== "calories");
  return (
    <article
      className={`relative flex flex-col justify-between gap-4 rounded-2xl border p-4 transition-all duration-200 sm:p-5 md:flex-row md:items-center ${
        isFirst
          ? "border-emerald-500/70 bg-gradient-to-r from-top-a via-top-b to-top-c shadow-[0_0_25px_rgb(var(--glow-1)/0.15)]"
          : "border-slate-800 bg-slate-900/70 hover:border-slate-700 hover:bg-slate-900"
      }`}
    >
      {/* 왼쪽: 순위·조합 이름·영양. 내용 폭만 쓰고(조합 이름은 한 줄), 남는 폭은 가운데 사진 칸이 쓴다. */}
      <div className="min-w-0 space-y-1.5 md:max-w-[420px] md:shrink-0">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-black ${
              isFirst ? "bg-emerald-400 text-on-accent shadow-[0_0_10px_rgb(var(--glow-2)/0.8)]" : "bg-slate-800 text-slate-300"
            }`}
          >
            TOP {row.rank}
          </span>
          <h3 className="min-w-0 truncate whitespace-nowrap text-base font-extrabold text-strong" title={comboTitle(row)}>
            {comboTitle(row)}
          </h3>
        </div>
        {tagline && <p className="text-xs font-medium text-slate-400">{tagline}</p>}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="rounded border border-emerald-800/60 bg-emerald-950/60 px-2 py-0.5 text-[11px] font-bold text-accent">
            총 단백질 {formatNutrient("protein", row.totals.protein)}
          </span>
          <span className="rounded bg-slate-800/80 px-2 py-0.5 text-[11px] font-semibold text-slate-400">
            열량 {formatNutrient("calories", row.totals.calories)}
          </span>
          {extra.map((key) => (
            <span key={key} className="rounded bg-slate-800/80 px-2 py-0.5 text-[11px] font-semibold text-slate-400">
              {NUTRIENTS[key].ko} {formatNutrient(key, row.totals[key])}
            </span>
          ))}
        </div>
      </div>

      {/* 가운데: 상품 사진. 조합 정보와 장바구니 사이의 남는 폭 가운데에 둔다. */}
      <div className="flex min-w-0 flex-1 items-center gap-3 overflow-x-auto px-2 pb-1 pt-2 md:justify-center">
        {row.items.map((product, index) => (
          <Fragment key={product.item_cd + index}>
            {index > 0 && <span className="text-sm font-black text-slate-600">+</span>}
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
              className="group/item flex shrink-0 cursor-pointer flex-col items-center rounded-xl"
            >
              <span className="relative block h-16 w-16 rounded-xl border border-slate-700/80 bg-slate-800 p-1 transition-all group-hover/item:border-emerald-400 group-hover/item:shadow-[0_0_12px_rgb(var(--glow-2)/0.3)] sm:h-[72px] sm:w-[72px]">
                <ProductImage url={product.image_url} alt="" />
                <span className="absolute -right-1.5 -top-1.5 rounded border border-slate-700 bg-slate-900 px-1 text-[9px] font-bold text-slate-200">
                  {formatWon(product.price)}
                </span>
              </span>
              <span className="mt-1 max-w-[80px] truncate text-center text-[11px] text-slate-400 group-hover/item:text-slate-200">
                {product.product_name}
              </span>
            </button>
          </Fragment>
        ))}
      </div>

      <div className="flex shrink-0 items-center justify-between gap-3 border-t border-slate-800 pt-2 md:justify-end md:border-t-0 md:pt-0">
        {/* 보조 기능이라 테두리를 강조하고 바탕은 옅게 둔다. 마우스를 올리면 채운다. 주 기능(AI 추천받기)은 cta로 칠한다. */}
        <button
          onClick={() => onAddToCart(row)}
          className="flex w-full flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-xl border-2 border-emerald-400 bg-emerald-500/10 px-4 py-2 font-bold text-accent-soft transition-all hover:bg-emerald-500 hover:text-on-accent active:scale-95 md:w-auto md:flex-initial"
        >
          <ShoppingCart className="h-4 w-4 stroke-[2.5]" />
          <span>장바구니</span>
          <span className="rounded bg-slate-950/30 px-1.5 py-0.5 text-xs font-black">{formatWon(row.total_price)}</span>
        </button>
      </div>
    </article>
  );
}

export function Results({ response, loading, onQuickReply, onCancelQuestion, onAddToCart, onHover, onHoverEnd }: Props) {
  const loadingMessage = useLoadingMessage(loading);
  if (loading) {
    // 이전 추천이 있어도 새 요청을 기다리는 동안에는 안내를 보여 준다.
    return (
      <Message icon={<Loader2 className="h-7 w-7 animate-spin" />}>
        <p>{loadingMessage}</p>
      </Message>
    );
  }
  // 오류와 "영양소 정보 없음"은 입력창 아래 안내(PromptForm)에 나온다.
  if (!response) {
    return (
      <Message icon={<Sparkles className="h-9 w-9 text-cta-mark" strokeWidth={1.5} />}>
        카테고리와 조건을 정하고 추천받기를 눌러주세요.
      </Message>
    );
  }
  if (response.status === "ask") {
    return (
      <Message icon={<HelpCircle className="h-7 w-7" />}>
        <p className="font-bold text-strong">{response.parsed.clarification_question}</p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {response.quick_replies.map((reply) => (
            <button
              key={reply}
              disabled={loading}
              onClick={() => onQuickReply(reply)}
              className="rounded-xl border border-cta/60 bg-cta/10 px-4 py-2 text-sm font-bold text-cta-fg transition-colors hover:bg-cta hover:text-cta-ink disabled:opacity-50"
            >
              {reply}
            </button>
          ))}
        </div>
        <button onClick={onCancelQuestion} className="mt-4 text-xs text-slate-400 underline hover:text-strong">
          처음부터 다시 적기
        </button>
      </Message>
    );
  }
  if (response.status === "empty" || response.results.length === 0) {
    return (
      <Message icon={<SearchX className="h-7 w-7" />}>
        조건에 맞는 상품을 찾지 못했어요. 예산을 늘리거나 카테고리를 바꿔 보세요.
      </Message>
    );
  }
  return (
    <section>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 px-1">
        <div className="flex items-center gap-2">
          <h2 className="flex items-center gap-2 text-xl font-bold tracking-tight text-strong">
            <Flame className="h-5 w-5 text-accent" />
            AI 추천{response.mode === "조합" ? " 조합" : ""} Top {response.results.length}
          </h2>
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">맞춤 큐레이션</span>
        </div>
        <div className="flex items-center gap-1 text-xs text-slate-400">
          <Info className="h-3.5 w-3.5 text-accent" />
          <span>사진에 마우스를 올리거나 누르면 6대 영양정보가 표시됩니다</span>
        </div>
      </div>
      {response.relaxed && <Notice>{response.relaxed.message}</Notice>}
      {response.notice && <Notice>{response.notice}</Notice>}
      <div className="space-y-3.5">
        {response.results.map((row) => (
          <ComboCard
            key={row.rank}
            row={row}
            parsed={response.parsed}
            goal={response.goal}
            onAddToCart={onAddToCart}
            onHover={onHover}
            onHoverEnd={onHoverEnd}
          />
        ))}
      </div>
    </section>
  );
}
