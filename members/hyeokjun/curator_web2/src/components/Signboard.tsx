/** 격자 바탕의 간판. 제목 양옆에 보라 선을 둔다. 제목을 누르면 처음 화면으로 돌아간다. */
export function Signboard({ onHome }: { onHome: () => void }) {
  return (
    <div className="sign-grid border-b border-panel-line/70">
      <div className="mx-auto flex max-w-5xl flex-col items-center px-4 py-8 sm:py-10">
        <div className="flex items-center gap-6 sm:gap-12">
          <span className="sign-line hidden translate-y-2 sm:block" aria-hidden />
          <button onClick={onHome} className="rounded-xl" aria-label="영양 편의점 메인으로">
            <span className="sign-title block whitespace-nowrap text-5xl font-black tracking-[0.14em] sm:text-7xl">
              영양 편의점
            </span>
          </button>
          <span className="sign-line hidden translate-y-2 sm:block" aria-hidden />
        </div>
        <p className="mt-3 whitespace-nowrap text-sm font-semibold tracking-wide text-slate-100 sm:text-xl">
          AI 맞춤 식단 &amp; 예산 매칭 서비스
        </p>
      </div>
    </div>
  );
}
