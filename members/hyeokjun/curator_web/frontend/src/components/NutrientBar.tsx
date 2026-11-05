import type { Direction, NutrientKey } from "@/api/types";
import { cn } from "@/utils/cn";
import { dailyPercent, formatNutrient, NUTRIENTS } from "@/utils/nutrition";

interface Props {
  nutrient: NutrientKey;
  value: number;
  direction?: Direction;
}

export function NutrientBar({ nutrient, value, direction }: Props) {
  const percent = dailyPercent(nutrient, value);
  const arrow = direction === "high" ? " ↑" : direction === "low" ? " ↓" : "";
  return (
    <div className="grid grid-cols-[76px_minmax(0,1fr)_auto] items-center gap-2 font-mono text-xs">
      <span className="text-muted">
        {NUTRIENTS[nutrient].ko}
        {arrow}
      </span>
      <span className="h-1.5 overflow-hidden rounded-chip bg-panel-2">
        <span
          className={cn("block h-full", direction === "low" ? "bg-sky" : "bg-lime")}
          style={{ width: `${Math.min(100, percent)}%` }}
        />
      </span>
      <span className="tnum text-right text-fg">
        {formatNutrient(nutrient, value)} · {percent}%
      </span>
    </div>
  );
}
