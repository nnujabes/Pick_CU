import type { RefObject } from "react";
import { AlertCircle, Info, Search, TriangleAlert, X } from "lucide-react";
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

/** 칩에는 짧은 이름을, 입력창에는 영양 조건이 들어간 문장을 넣는다. 예산만 있는 문장은 영양소를 알 수 없어서다. */
const EXAMPLES = [
  { label: "고단백 식단", text: "운동 후에 먹을 고단백 식단 추천해줘" },
  { label: "가볍게 한 끼", text: "가볍게 한 끼 먹을 저칼로리 음식 추천해줘" },
  { label: "1만 원 이하", text: "1만 원 이하로 든든한 한 끼 추천해줘" },
];

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
    <section className="mb-10">
      <label htmlFor="prompt" className="mb-4 flex items-center gap-3 px-1 text-lg font-bold text-white sm:text-xl">
        <StepNumber value={2} />
        추천 조건 입력
      </label>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
        className="flex flex-col gap-3 sm:flex-row"
      >
        <div className="relative flex flex-1 items-center rounded-xl border border-panel-line bg-panel transition-colors focus-within:border-cta/70">
          <Search className="absolute left-5 h-5 w-5 text-slate-400" />
          <input
            id="prompt"
            ref={inputRef}
            type="text"
            value={value}
            maxLength={300}
            aria-describedby={notice ? "prompt-notice" : undefined}
            aria-invalid={notice?.tone === "warn" || notice?.tone === "error" ? true : undefined}
            onChange={(event) => onChange(event.target.value)}
            placeholder={answering ? "위 질문의 답을 적어 주세요" : "예: 운동 후 먹을 1만 원 미만의 음식을 추천해줘"}
            className="w-full bg-transparent py-4 pl-14 pr-12 text-base text-white placeholder-slate-500 outline-none focus-visible:outline-none sm:text-lg"
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
          className="flex items-center justify-center whitespace-nowrap rounded-xl bg-cta px-10 py-4 text-lg font-extrabold text-cta-ink transition-transform duration-150 hover:bg-cta-hover active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "찾는 중…" : "AI 추천받기"}
        </button>
      </form>
      <div aria-live="polite">
        {notice && (
          <p
            id="prompt-notice"
            role={notice.tone === "error" ? "alert" : undefined}
            className={`mt-3 flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold ${NOTICE_STYLE[notice.tone].box}`}
          >
            {NOTICE_STYLE[notice.tone].icon}
            <span>{notice.text}</span>
          </p>
        )}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 px-1 sm:gap-3">
        <span className="text-sm text-slate-400">예시로 시도해보세요.</span>
        <span className="h-4 w-px bg-slate-600" aria-hidden />
        {EXAMPLES.map((example) => (
          <button
            key={example.label}
            type="button"
            disabled={loading}
            title={example.text}
            onClick={() => {
              onChange(example.text);
              inputRef.current?.focus();
            }}
            className="rounded-full border border-panel-line bg-panel px-4 py-1.5 text-sm text-slate-200 transition-colors hover:border-cta/70 hover:text-white disabled:opacity-50"
          >
            {example.label}
          </button>
        ))}
      </div>
    </section>
  );
}
