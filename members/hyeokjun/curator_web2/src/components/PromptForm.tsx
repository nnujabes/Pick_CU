import type { RefObject } from "react";
import { AlertCircle, Info, Search, Sparkles, TriangleAlert, X } from "lucide-react";
import { StepNumber } from "./CategoryPicker";

/** 입력창 바로 아래에 띄우는 안내. 경우에 따라 안내(info)·주의(warn)·오류(error)로 나눈다. */
export interface InputNotice {
  tone: "info" | "warn" | "error";
  text: string;
}

const NOTICE_STYLE: Record<InputNotice["tone"], { box: string; icon: JSX.Element }> = {
  info: {
    box: "border-sky-500/40 bg-sky-950/40 text-sky-200",
    icon: <Info className="h-4 w-4 shrink-0" />,
  },
  warn: {
    box: "border-amber-500/50 bg-amber-950/40 text-amber-200",
    icon: <TriangleAlert className="h-4 w-4 shrink-0" />,
  },
  error: {
    box: "border-rose-500/50 bg-rose-950/40 text-rose-200",
    icon: <AlertCircle className="h-4 w-4 shrink-0" />,
  },
};

interface Props {
  value: string;
  answering: boolean;
  loading: boolean;
  notice: InputNotice | null;
  inputRef: RefObject<HTMLInputElement>;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function PromptForm({ value, answering, loading, notice, inputRef, onChange, onSubmit }: Props) {
  return (
    <section className="mb-8">
      <label htmlFor="prompt" className="mb-2 flex items-center gap-2 px-1 text-sm font-semibold text-slate-300">
        <StepNumber value={2} />
        추천 조건 입력
      </label>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
        className="flex flex-col gap-2 rounded-2xl border border-slate-700/80 bg-slate-900/80 p-2 shadow-[0_4px_25px_rgba(0,0,0,0.5)] focus-within:border-emerald-500/70 sm:flex-row"
      >
        <div className="relative flex flex-1 items-center">
          <Search className="absolute left-4 h-5 w-5 text-slate-400" />
          <input
            id="prompt"
            ref={inputRef}
            type="text"
            value={value}
            maxLength={300}
            aria-describedby={notice ? "prompt-notice" : undefined}
            aria-invalid={notice?.tone === "warn" || notice?.tone === "error" ? true : undefined}
            onChange={(event) => onChange(event.target.value)}
            placeholder={answering ? "위 질문의 답을 적어 주세요" : "예: 운동후에 먹을 1만원 미만의 단백질 음식을 추천해줘"}
            className="w-full bg-transparent py-3 pl-12 pr-12 text-sm text-white placeholder-slate-500 outline-none focus-visible:outline-none sm:text-base"
          />
          {value && (
            <button
              type="button"
              aria-label="입력한 문장 모두 지우기"
              title="모두 지우기"
              // 누르는 동안 입력창의 포커스를 빼앗지 않는다.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onChange("");
                inputRef.current?.focus();
              }}
              className="absolute right-3 flex h-7 w-7 items-center justify-center rounded-full bg-slate-700/80 text-slate-300 transition-colors hover:bg-slate-600 hover:text-white"
            >
              <X className="h-4 w-4 stroke-[2.5]" />
            </button>
          )}
        </div>
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="flex items-center justify-center gap-2 rounded-xl bg-cta px-7 py-3.5 font-extrabold text-cta-ink shadow-[0_0_24px_rgba(212,242,122,0.45)] transition-transform duration-150 hover:bg-cta-hover active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Sparkles className="h-4 w-4 fill-cta-ink" />
          <span>{loading ? "찾는 중…" : "AI 추천받기"}</span>
        </button>
      </form>
      <div aria-live="polite">
        {notice && (
          <p
            id="prompt-notice"
            role={notice.tone === "error" ? "alert" : undefined}
            className={`mt-2 flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold ${NOTICE_STYLE[notice.tone].box}`}
          >
            {NOTICE_STYLE[notice.tone].icon}
            <span>{notice.text}</span>
          </p>
        )}
      </div>
    </section>
  );
}
