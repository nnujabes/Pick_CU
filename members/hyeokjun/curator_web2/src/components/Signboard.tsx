import { ShoppingBag } from "lucide-react";

export function Signboard({ onHome }: { onHome: () => void }) {
  return (
    <div className="mb-8 text-center">
      <button onClick={onHome} className="group inline-block rounded-2xl" aria-label="Pick CU 메인으로">
        <div className="relative inline-flex flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-purple-500/80 bg-gradient-to-b from-[#131b2e] to-[#0d1322] p-5 px-10 shadow-[0_0_35px_rgba(168,85,247,0.35)] transition-transform duration-200 group-hover:scale-[1.02]">
          <div className="mb-2 flex gap-2">
            <div className="h-1.5 w-10 rounded-full bg-purple-500 shadow-[0_0_8px_#a855f7]" />
            <div className="h-1.5 w-16 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
            <div className="h-1.5 w-10 rounded-full bg-purple-500 shadow-[0_0_8px_#a855f7]" />
          </div>
          <div className="flex items-center gap-3">
            <div className="rounded-xl border border-purple-400/50 bg-purple-950/80 p-2 shadow-[0_0_12px_rgba(168,85,247,0.6)]">
              <ShoppingBag className="h-7 w-7 text-emerald-400" />
            </div>
            <h1 className="text-3xl font-black tracking-tight text-white drop-shadow-[0_0_15px_rgba(52,211,153,0.8)] sm:text-4xl">
              Pick CU
            </h1>
          </div>
          <p className="mt-1 text-xs font-semibold tracking-wider text-emerald-300 drop-shadow-[0_0_8px_rgba(16,185,129,0.6)] sm:text-sm">
            AI 맞춤 식단 &amp; 예산 매칭 서비스
          </p>
        </div>
      </button>
    </div>
  );
}
