import { Check, Cookie, CookingPot, CupSoda, IceCreamCone, Milk, Soup, type LucideIcon } from "lucide-react";
import type { Category } from "@/api/types";
import { CATEGORIES } from "@/utils/format";

const ICONS: Record<Category, LucideIcon> = {
  간편식사: Soup,
  즉석조리: CookingPot,
  과자류: Cookie,
  아이스크림: IceCreamCone,
  식품: Milk,
  음료: CupSoda,
};

export function StepNumber({ value }: { value: number }) {
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cta text-sm font-extrabold text-cta-ink">
      {value}
    </span>
  );
}

export function CategoryPicker({ selected, onToggle }: { selected: Category[]; onToggle: (category: Category) => void }) {
  return (
    <section className="mb-10">
      <div className="mb-4 flex items-center justify-between gap-2 px-1">
        <h2 className="flex items-center gap-3 text-lg font-bold text-white sm:text-xl">
          <StepNumber value={1} />
          카테고리 선택 <span className="text-xs font-normal text-slate-400 sm:text-sm">(1~3개 선택 가능)</span>
        </h2>
        <span className="shrink-0 rounded-lg border border-cta/60 px-3 py-1 text-xs font-semibold text-cta sm:text-sm">
          {selected.length} / 3 선택됨
        </span>
      </div>

      {/* 어느 폭에서나 한 줄이다. */}
      <div className="grid grid-cols-6 gap-1.5 sm:gap-3">
        {CATEGORIES.map((category) => {
          const isSelected = selected.includes(category);
          const Icon = ICONS[category];
          return (
            <button
              key={category}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onToggle(category)}
              className={`relative flex min-w-0 flex-col items-center justify-center gap-1.5 rounded-xl border px-0 py-3 transition-colors duration-200 sm:gap-2 sm:py-5 ${
                isSelected
                  ? "border-cta bg-cta-soft text-white shadow-[0_0_0_1px_rgba(79,216,168,0.25)]"
                  : "border-panel-line bg-panel text-slate-300 hover:border-slate-500 hover:text-white"
              }`}
            >
              {isSelected && (
                <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-cta sm:right-2 sm:top-2 sm:h-5 sm:w-5">
                  <Check className="h-3 w-3 stroke-[3] text-cta-ink sm:h-3.5 sm:w-3.5" />
                </span>
              )}
              <Icon className="h-6 w-6 sm:h-8 sm:w-8" strokeWidth={1.5} />
              <span className="whitespace-nowrap text-[10px] font-semibold tracking-[-0.04em] sm:text-base sm:tracking-normal">
                {category}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
