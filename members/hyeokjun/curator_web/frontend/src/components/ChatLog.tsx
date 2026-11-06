import { useEffect, useRef } from "react";
import type { RecommendResponse } from "@/api/types";
import { useLoadingMessage } from "@/hooks/useLoadingMessage";
import { activeConditions, formatWon, NUTRIENTS } from "@/utils/nutrition";

export type ChatMessage =
  | { id: number; who: "user"; text: string }
  | { id: number; who: "bot"; response: RecommendResponse }
  | { id: number; who: "error"; text: string };

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  onQuickReply: (text: string) => void;
}

const Who = ({ children }: { children: string }) => (
  <span className="mb-1 block font-mono text-[11px] tracking-[0.05em] text-dim">{children}</span>
);

function Tag({ tone = "plain", children }: { tone?: "plain" | "cond" | "goal"; children: React.ReactNode }) {
  const toneClass = {
    plain: "border-line text-fg",
    cond: "border-[#5d6b37] text-lime",
    goal: "border-[#5a4a33] text-warm",
  }[tone];
  return <span className={`tnum rounded-btn border bg-panel-2 px-2 py-1 font-mono text-[12.5px] ${toneClass}`}>{children}</span>;
}

function ParsedChips({ response }: { response: RecommendResponse }) {
  const { parsed, goal } = response;
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {goal && <Tag tone="goal">{goal}</Tag>}
      {activeConditions(parsed).map(({ key, direction }) => (
        <Tag key={key} tone="cond">
          {NUTRIENTS[key].ko} {direction === "high" ? "↑" : "↓"}
        </Tag>
      ))}
      {parsed.budget != null && <Tag>{formatWon(parsed.budget)} 이하</Tag>}
      {parsed.count != null && <Tag>{parsed.count}개</Tag>}
      {parsed.price_priority && <Tag>가격대비</Tag>}
    </div>
  );
}

function ModelJson({ response }: { response: RecommendResponse }) {
  return (
    <details className="mt-2">
      <summary className="font-mono text-xs text-muted">모델 출력(JSON) 보기</summary>
      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-card border border-line bg-[#1c1d1a] p-3 font-mono text-xs text-[#d9dbcf]">
        {JSON.stringify(response.parsed, null, 1)}
      </pre>
    </details>
  );
}

function BotMessage({ response, isLast, onQuickReply }: {
  response: RecommendResponse;
  isLast: boolean;
  onQuickReply: (text: string) => void;
}) {
  if (response.status === "ask") {
    return (
      <>
        <p>{response.parsed.clarification_question}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {response.quick_replies.map((reply) => (
            <button
              key={reply}
              type="button"
              disabled={!isLast}
              onClick={() => onQuickReply(reply)}
              className="rounded-chip border border-lime px-3 py-1 text-[13.5px] text-lime transition-colors hover:bg-lime hover:text-lime-ink disabled:border-line disabled:text-dim disabled:hover:bg-transparent disabled:hover:text-dim"
            >
              {reply}
            </button>
          ))}
        </div>
        <ModelJson response={response} />
      </>
    );
  }
  const found = [...new Set(response.results.flatMap((row) => row.items.map((item) => item.category)))];
  return (
    <>
      <p>이렇게 이해했어요.</p>
      <ParsedChips response={response} />
      <p className="mt-2 text-[13.5px] text-muted">
        {response.status === "ok"
          ? `${found.join(" · ")}에서 ${response.results.length}개를 찾았어요.`
          : "조건에 맞는 상품을 찾지 못했어요. 예산을 늘리거나 카테고리를 바꿔 볼까요?"}
      </p>
      <ModelJson response={response} />
    </>
  );
}

export function ChatLog({ messages, loading, onQuickReply }: Props) {
  const logRef = useRef<HTMLDivElement>(null);
  const loadingMessage = useLoadingMessage(loading);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, loading, loadingMessage]);

  return (
    <div ref={logRef} className="chat-log flex flex-col gap-3 pr-1" role="log" aria-live="polite" aria-label="대화 기록">
      {!messages.length && (
        <div className="chat-hint-box">
          <p className="chat-hint text-muted" data-chat-hint>
            예산, 영양, 지금 상황을 편하게 적어 주세요. 고른 카테고리 안에서 찾아 드려요.
          </p>
        </div>
      )}
      {messages.map((message, index) => {
        if (message.who === "user") {
          return (
            <div key={message.id} className="min-w-0 max-w-[85%] break-words self-end rounded-card border border-line bg-panel-2 px-4 py-3">
              <Who>나</Who>
              {message.text}
            </div>
          );
        }
        if (message.who === "error") {
          return (
            <div key={message.id} className="min-w-0 max-w-[85%] break-words self-start rounded-card border border-alert px-4 py-3 text-alert">
              <Who>Pick CU</Who>
              {message.text}
            </div>
          );
        }
        return (
          <div key={message.id} className="min-w-0 max-w-[85%] break-words self-start rounded-card border border-line px-4 py-3">
            <Who>Pick CU</Who>
            <BotMessage
              response={message.response}
              isLast={index === messages.length - 1}
              onQuickReply={onQuickReply}
            />
          </div>
        );
      })}
      {loading && <p className="self-start font-mono text-[13px] text-muted">{loadingMessage}</p>}
    </div>
  );
}
