function Stripes() {
  return (
    <div className="hidden min-w-0 flex-1 flex-col gap-2 sm:flex" aria-hidden>
      <span className="sign-stripe h-5 bg-lime-200 md:h-7" />
      <span className="sign-stripe h-5 bg-lime-400 md:h-8" />
      <span className="sign-stripe h-5 bg-violet-600 md:h-7" />
    </div>
  );
}

/** 벽돌 벽에 단 네온 간판. 깜빡이지 않는다. */
export function Signboard({ onHome }: { onHome: () => void }) {
  return (
    <div className="sign-wall border-b-4 border-[#10162a]">
      <div className="mx-auto flex max-w-5xl items-center justify-center gap-4 px-4 py-6">
        <Stripes />
        <button onClick={onHome} className="group shrink-0 rounded-2xl" aria-label="영양 편의점 메인으로">
          <span className="sign-board block rounded-2xl px-6 py-4 transition-transform duration-200 group-hover:scale-[1.02] sm:px-10">
            <span className="sign-neon block whitespace-nowrap text-5xl font-black sm:text-6xl">영양 편의점</span>
            <span className="mt-2 block whitespace-nowrap text-center text-xs font-semibold text-white sm:text-base">
              AI 맞춤 식단 &amp; 예산 매칭 서비스
            </span>
          </span>
        </button>
        <Stripes />
      </div>
    </div>
  );
}
