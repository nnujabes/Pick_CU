import { Check, CupSoda, Drumstick, Ham, IceCreamCone, type LucideIcon } from "lucide-react";
import type { SVGProps } from "react";
import type { Category } from "@/api/types";
import { CATEGORIES, CATEGORY_DETAILS } from "@/utils/format";

type IconProps = SVGProps<SVGSVGElement> & { strokeWidth?: number };

/** 과자 봉지: 위아래가 접힌 봉지에 둥근 무늬. lucide에 없어 같은 24px 선 아이콘으로 그렸다. */
export function SnackBag({ strokeWidth = 1.5, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M4.5 3h15l-.7 2.4.7 2.4v8.4l-.7 2.4.7 2.4h-15l.7-2.4-.7-2.4V7.8l.7-2.4z" />
      <path d="M5.2 5.6h13.6M5.2 18.4h13.6" />
      <circle cx="12" cy="12" r="3.3" />
      <path d="M10.3 12.8c.8-1.2 2.1-1.5 3.3-1" />
    </svg>
  );
}

/** 도시락: 위에 젓가락, 칸이 나뉜 도시락통. 밥 칸(왼쪽, 밥알)과 반찬 칸 두 개(오른쪽). */
export function LunchBox({ strokeWidth = 1.5, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M4 5.5 20 2.5M4 7.5l16-2" />
      <rect x="2.5" y="9" width="19" height="12" rx="3" />
      <path d="M12 9v12" />
      <path d="M12 15h9.5" />
      <path d="M5.5 13h.01M8.5 13h.01M7 16h.01M5.5 18.5h.01M8.5 18.5h.01" strokeWidth={2.25} />
    </svg>
  );
}

/** 세부 분류를 대표하는 아이콘: 간편식사 = 도시락, 즉석조리 = 튀김, 식품 = 햄(가공식사·안주) */
export const CATEGORY_ICONS: Record<Category, LucideIcon | ((props: IconProps) => JSX.Element)> = {
  간편식사: LunchBox,
  즉석조리: Drumstick,
  과자류: SnackBag,
  아이스크림: IceCreamCone,
  식품: Ham,
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
        <h2 className="flex items-center gap-3 text-lg font-bold text-strong sm:text-xl">
          <StepNumber value={1} />
          카테고리 선택 <span className="hidden text-sm font-normal text-slate-400 sm:inline">(1~3개 선택 가능)</span>
        </h2>
        <span className="count-pill shrink-0 rounded-lg px-3 py-1 text-xs font-semibold sm:text-sm">
          {selected.length} / 3 선택됨
        </span>
      </div>

      {/* 휴대폰 폭은 3칸씩 두 줄, 넓은 폭은 한 줄이다. */}
      <div className="relative grid grid-cols-3 gap-2 sm:grid-cols-6 sm:gap-3">
        {CATEGORIES.map((category, index) => {
          const isSelected = selected.includes(category);
          const Icon = CATEGORY_ICONS[category];
          const details = CATEGORY_DETAILS[category];
          const tipId = `category-tip-${index}`;
          // 말풍선이 화면 밖으로 나가지 않게 한다. 휴대폰 폭은 카테고리 줄 전체의 가운데, 그보다 넓으면 카드 기준(양 끝 카드는 카드 끝)이다.
          const edge = index === 0 ? "sm:left-0 sm:translate-x-0" : index === CATEGORIES.length - 1 ? "sm:left-auto sm:right-0 sm:translate-x-0" : "";
          const align = `left-1/2 -translate-x-1/2 ${edge}`;
          return (
            <div key={category} className="group min-w-0 sm:relative">
              <button
                type="button"
                aria-pressed={isSelected}
                aria-describedby={tipId}
                onClick={() => onToggle(category)}
                className={`relative flex w-full min-w-0 flex-col items-center justify-center gap-1.5 rounded-xl border px-0 py-3 transition-colors duration-200 sm:gap-2 sm:py-5 ${
                  isSelected
                    ? "border-cta-mark bg-cta-soft text-strong shadow-[0_0_0_1px_rgb(var(--glow-3)/0.25)]"
                    : "border-panel-line bg-panel text-slate-300 hover:border-slate-500 hover:text-strong"
                }`}
              >
                {isSelected && (
                  <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-cta-mark sm:right-2 sm:top-2 sm:h-5 sm:w-5">
                    <Check className="h-3 w-3 stroke-[3] text-cta-check sm:h-3.5 sm:w-3.5" />
                  </span>
                )}
                <Icon className="h-6 w-6 sm:h-8 sm:w-8" strokeWidth={1.5} />
                <span className="whitespace-nowrap text-sm font-semibold sm:text-base">
                  {category}
                </span>
              </button>

              {/* 세부 분류 말풍선: 마우스를 올리거나 키보드로 고르면 보인다. */}
              <div
                id={tipId}
                role="tooltip"
                className={`pointer-events-none invisible absolute top-full z-30 mt-2 w-max rounded-xl border-2 border-cta/80 bg-tip/95 p-3 opacity-0 shadow-[0_0_20px_rgb(var(--glow-3)/0.25)] transition-opacity duration-150 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100 ${align}`}
              >
                <p className="mb-2 border-b border-panel-line pb-1.5 text-xs font-bold text-strong">
                  {category} <span className="font-normal text-slate-400">세부 분류</span>
                </p>
                {/* 세부 분류는 항상 한 줄로 둔다. */}
                <ul className="flex flex-nowrap gap-1.5">
                  {details.map((detail) => (
                    <li key={detail} className="whitespace-nowrap rounded-md bg-cta-soft px-2 py-0.5 text-xs font-semibold text-cta-fg">
                      {detail}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
