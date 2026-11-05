import { useEffect, useState } from "react";
import type { Category } from "@/api/types";
import { cn } from "@/utils/cn";
import { CATEGORIES } from "@/utils/nutrition";

const MAX_CATEGORIES = 3;

interface Props {
  selected: Category[];
  counts: Partial<Record<Category, number>>;
  warning: string | null;
  onChange: (next: Category[]) => void;
}

export function CategoryChips({ selected, counts, warning, onChange }: Props) {
  const [shaking, setShaking] = useState<Category | null>(null);
  const [limitHit, setLimitHit] = useState(false);

  useEffect(() => {
    if (!shaking) return;
    const timer = window.setTimeout(() => setShaking(null), 340);
    return () => window.clearTimeout(timer);
  }, [shaking]);

  function toggle(category: Category) {
    if (selected.includes(category)) {
      setLimitHit(false);
      onChange(selected.filter((item) => item !== category));
    } else if (selected.length >= MAX_CATEGORIES) {
      setShaking(category);
      setLimitHit(true);
    } else {
      setLimitHit(false);
      onChange([...selected, category]);
    }
  }

  const message = limitHit
    ? "카테고리는 3개까지 고를 수 있어요."
    : warning ?? (selected.length ? `${selected.join(" · ")}에서 찾아요.` : "카테고리를 하나 이상 골라 주세요.");
  const isWarning = limitHit || Boolean(warning) || !selected.length;

  return (
    <div>
      <p className="mb-2 font-mono text-xs tracking-[0.06em] text-muted">카테고리 · 1~3개</p>
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((category) => {
          const active = selected.includes(category);
          return (
            <button
              key={category}
              type="button"
              aria-pressed={active}
              onClick={() => toggle(category)}
              className={cn(
                "inline-flex items-center gap-2 rounded-chip border px-4 py-2 text-sm transition-colors",
                active
                  ? "border-lime bg-lime font-medium text-lime-ink"
                  : "border-line bg-panel text-fg hover:border-muted",
                shaking === category && "animate-shake border-alert",
              )}
            >
              {category}
              {counts[category] != null && (
                <span className="tnum font-mono text-xs opacity-70">{counts[category]!.toLocaleString("ko-KR")}</span>
              )}
            </button>
          );
        })}
      </div>
      <p role="status" className={cn("mt-2 min-h-5 text-[13px]", isWarning ? "text-alert" : "text-muted")}>
        {message}
      </p>
    </div>
  );
}
