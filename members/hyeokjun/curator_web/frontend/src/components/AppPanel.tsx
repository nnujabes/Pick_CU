import { forwardRef, useState } from "react";
import type { Category, MockCase } from "@/api/types";
import { Button } from "@/components/ui/button";
import { CategoryChips } from "./CategoryChips";
import { ChatLog, type ChatMessage } from "./ChatLog";

export const SAMPLES: { text: string; categories?: Category[] }[] = [
  { text: "하체 운동 끝났는데 5천원으로 두 개", categories: ["식품", "음료"] },
  { text: "다이어트 중인데 덜 단 음료", categories: ["음료"] },
  { text: "어제 회식했더니 얼굴이 부었어", categories: ["간편식사", "식품"] },
  { text: "가성비 좋은 단백질 간식 3천원", categories: ["과자류"] },
  { text: "운동 끝났는데 뭐 먹지" },
];

const MOCK_CASES: { key: MockCase; label: string }[] = [
  { key: "single", label: "단품" },
  { key: "combo", label: "조합" },
  { key: "ask", label: "되묻기" },
  { key: "empty", label: "결과 없음" },
  { key: "relaxed", label: "조건 완화" },
];

interface Props {
  categories: Category[];
  categoryWarning: string | null;
  messages: ChatMessage[];
  loading: boolean;
  onCategories: (next: Category[]) => void;
  onAsk: (text: string) => void;
  onQuickReply: (text: string) => void;
  onSample: (sample: (typeof SAMPLES)[number]) => void;
  onMock: (mock: MockCase) => void;
}

export const AppPanel = forwardRef<HTMLInputElement, Props>(
  ({ categories, categoryWarning, messages, loading, onCategories, onAsk, onQuickReply, onSample, onMock }, inputRef) => {
    const [text, setText] = useState("");

    function submit(event: React.FormEvent) {
      event.preventDefault();
      if (!text.trim() || loading) return;
      onAsk(text.trim());
      setText("");
    }

    return (
      <section id="app-panel" className="app-panel" aria-label="추천 대화">
        <h2 data-panel-title className="text-[26px] font-bold leading-tight tracking-[-0.02em]">무엇을 찾아 드릴까요?</h2>
        <CategoryChips selected={categories} warning={categoryWarning} onChange={onCategories} />
        <ChatLog messages={messages} loading={loading} onQuickReply={onQuickReply} />
        {import.meta.env.DEV && (
          <details className="font-mono text-xs text-dim">
            <summary>mock 응답 확인 (개발용)</summary>
            <div className="mt-2 flex flex-wrap gap-2">
              {MOCK_CASES.map((mock) => (
                <Button key={mock.key} size="sm" variant="ghost" disabled={loading} onClick={() => onMock(mock.key)}>
                  {mock.label}
                </Button>
              ))}
            </div>
          </details>
        )}
        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((sample) => (
            <button
              key={sample.text}
              type="button"
              disabled={loading}
              onClick={() => onSample(sample)}
              className="rounded-btn border border-dashed border-line px-3 py-1 text-[13px] text-muted transition-colors hover:border-muted hover:text-fg"
            >
              {sample.text}
            </button>
          ))}
        </div>
        <form onSubmit={submit} data-prompt-form className="flex gap-2 rounded-card border border-muted bg-panel-2 p-2 focus-within:border-lime">
          <input
            ref={inputRef}
            value={text}
            maxLength={300}
            onChange={(event) => setText(event.target.value)}
            placeholder="예: 운동 후에 먹을 거 8천원으로"
            aria-label="요청 입력"
            className="min-w-0 flex-1 bg-transparent px-3 py-3 text-[17px] text-fg outline-none placeholder:text-muted"
          />
          <Button variant="lime" type="submit" disabled={loading || !text.trim()}>
            추천
          </Button>
        </form>
      </section>
    );
  },
);
AppPanel.displayName = "AppPanel";
