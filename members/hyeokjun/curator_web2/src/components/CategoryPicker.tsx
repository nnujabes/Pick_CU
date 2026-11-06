import { Check } from "lucide-react";
import type { Category } from "@/api/types";
import { CATEGORIES } from "@/utils/format";

export function StepNumber({ value }: { value: number }) {
  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-xs font-bold text-emerald-400">
      {value}
    </span>
  );
}

export function CategoryPicker({ selected, onToggle }: { selected: Category[]; onToggle: (category: Category) => void }) {
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <StepNumber value={1} />
          카테고리 선택 <span className="text-xs font-normal text-slate-400">(1~3개 선택 가능)</span>
        </h2>
        <span className="shrink-0 rounded-md border border-emerald-800/60 bg-emerald-950/50 px-2 py-0.5 text-xs font-semibold text-emerald-400">
          {selected.length} / 3 선택됨
        </span>
      </div>

      {/* 어느 폭에서나 한 줄이다. */}
      <div className="grid grid-cols-6 gap-1 sm:gap-2">
        {CATEGORIES.map((category) => {
          const isSelected = selected.includes(category);
          return (
            <button
              key={category}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onToggle(category)}
              className={`flex min-w-0 items-center justify-center gap-1.5 rounded-xl border px-0 py-3 text-[10px] font-bold tracking-[-0.06em] transition-all duration-200 sm:px-1 sm:text-sm sm:tracking-normal md:px-3 ${
                isSelected
                  ? // 이전 초록 계열을 채우되 명도·채도를 낮춰, 가장 밝은 AI 추천받기(cta)보다 눈에 덜 띄게 한다.
                    // 테두리는 강조하지 않는다(투명 테두리로 크기만 맞춘다).
                    "border-transparent bg-gradient-to-r from-[#14855a] to-[#11807a] text-[#effcf5]"
                  : "border-slate-800 bg-slate-900/90 text-slate-400 hover:border-slate-600 hover:text-slate-200"
              }`}
            >
              {isSelected && <Check className="hidden h-4 w-4 stroke-[3] md:block" />}
              <span className="whitespace-nowrap">{category}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
