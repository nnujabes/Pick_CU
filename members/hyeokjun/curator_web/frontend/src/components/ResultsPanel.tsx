import type { RecommendResponse, ResultRow } from "@/api/types";
import { Button } from "@/components/ui/button";
import { ResultCard } from "./ResultCard";

export type ResultsState =
  | { kind: "first" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "response"; id: number; response: RecommendResponse };

interface Props {
  state: ResultsState;
  selectedKey: string | null;
  onSelect: (row: ResultRow) => void;
  onAdd: (row: ResultRow) => void;
  onReview: (row: ResultRow) => void;
  onShowStore: () => void;
}

/** 빈 상태를 영수증처럼 보여 준다. 줄 값은 아직 비어 있다는 표시다. */
function Receipt({ title, lines, children }: { title: string; lines: [string, string][]; children: React.ReactNode }) {
  return (
    <div className="rounded-card border border-dashed border-line p-6">
      <p className="font-mono text-sm font-bold text-fg">{title}</p>
      <dl className="mt-3 grid max-w-[320px] gap-1 font-mono text-[13px] text-dim">
        {lines.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 border-b border-dotted border-line pb-1">
            <dt>{label}</dt>
            <dd className="tnum">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 max-w-[30em] text-sm text-muted">{children}</p>
    </div>
  );
}

function Heading({ title, meta }: { title: string; meta?: string }) {
  return (
    <div className="flex flex-wrap items-baseline gap-3">
      <h3 className="text-xl font-bold tracking-[-0.01em]">{title}</h3>
      {meta && <span className="text-[13px] text-muted">{meta}</span>}
    </div>
  );
}

export function ResultsPanel({ state, selectedKey, onSelect, onAdd, onReview, onShowStore }: Props) {
  if (state.kind === "first") {
    return (
      <section aria-label="추천 결과">
        <Heading title="추천 결과" />
        <div className="h-3" />
        <Receipt title="아직 주문이 없어요" lines={[["추천", "- 개"], ["합계", "- 원"], ["단백질", "- g"]]}>
          문장을 입력하면 여기에 추천 5개가 나와요.
        </Receipt>
      </section>
    );
  }
  if (state.kind === "loading") {
    return (
      <section aria-label="추천 결과" aria-busy="true">
        <Heading title="추천 결과" />
        <div className="h-3" />
        <div className="grid gap-3">
          {[0, 1, 2].map((key) => (
            <div key={key} className="h-28 animate-pulse rounded-card border border-line bg-panel" />
          ))}
        </div>
      </section>
    );
  }
  if (state.kind === "error") {
    return (
      <section aria-label="추천 결과">
        <Heading title="추천 결과" />
        <div className="h-3" />
        <div className="rounded-card border border-alert p-6 text-sm text-alert">{state.message}</div>
      </section>
    );
  }

  const { response } = state;
  if (response.status === "ask") {
    return (
      <section aria-label="추천 결과">
        <Heading title="추천 결과" />
        <div className="h-3" />
        <Receipt title="되묻는 중이에요" lines={[["기준", "확인 중"], ["추천", "대기"]]}>
          왼쪽 질문에 답하면 추천이 나와요.
        </Receipt>
      </section>
    );
  }
  if (response.status === "empty") {
    return (
      <section aria-label="추천 결과">
        <Heading title="추천 결과" />
        <div className="h-3" />
        <Receipt
          title="조건에 맞는 상품이 없어요"
          lines={[
            ["예산", response.parsed.budget != null ? `${response.parsed.budget.toLocaleString("ko-KR")}원` : "-"],
            ["찾은 조합", "0 개"],
          ]}
        >
          예산을 늘리거나 카테고리 수를 줄여 보세요. 카테고리마다 1개씩 담기 때문에 카테고리가 많을수록 합계가 커져요.
        </Receipt>
      </section>
    );
  }

  return (
    <section aria-label="추천 결과" className="results-fill" data-results-fill>
      <div className="flex flex-wrap items-center gap-2">
        <Heading title={`추천 ${response.results.length}개`} meta={`${response.mode} · 1일 기준치 대비 %`} />
        <Button size="sm" className="ml-auto py-1" onClick={onShowStore}>
          편의점 보기
        </Button>
      </div>
      {response.relaxed && (
        <p className="rounded-card border border-[#5a4a33] px-3 py-1 text-[13px] text-warm">
          {response.relaxed.message}
        </p>
      )}
      {response.notice && <p className="text-[13px] text-muted">{response.notice}</p>}
      <div key={state.id} className="result-list" data-result-list>
        {response.results.map((row, index) => {
          const key = row.items.map((item) => item.item_cd).join("-");
          return (
            <ResultCard
              key={key}
              row={row}
              parsed={response.parsed}
              index={index}
              selected={selectedKey === key}
              onSelect={onSelect}
              onAdd={onAdd}
              onReview={onReview}
            />
          );
        })}
      </div>
    </section>
  );
}
