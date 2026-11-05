import type { RefObject } from "react";
import { Search, Sparkles } from "lucide-react";
import { StepNumber } from "./CategoryPicker";

interface Props {
  value: string;
  answering: boolean;
  loading: boolean;
  inputRef: RefObject<HTMLInputElement>;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function PromptForm({ value, answering, loading, inputRef, onChange, onSubmit }: Props) {
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
            onChange={(event) => onChange(event.target.value)}
            placeholder={answering ? "위 질문의 답을 적어 주세요" : "예: 운동후에 먹을 1만원 미만의 단백질 음식을 추천해줘"}
            className="w-full bg-transparent py-3 pl-12 pr-4 text-sm text-white placeholder-slate-500 outline-none focus-visible:outline-none sm:text-base"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="flex items-center justify-center gap-2 rounded-xl bg-emerald-400 px-6 py-3.5 font-extrabold text-slate-950 shadow-[0_0_20px_rgba(52,211,153,0.4)] transition-transform duration-150 hover:bg-emerald-300 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Sparkles className="h-4 w-4 fill-slate-950" />
          <span>{loading ? "찾는 중…" : "AI 추천받기"}</span>
        </button>
      </form>
    </section>
  );
}
