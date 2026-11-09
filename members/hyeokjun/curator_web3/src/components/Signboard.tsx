/** 간판. 제목 양옆에 선을 둔다(다크 보라, 화이트 노랑). 제목을 누르면 처음 화면으로 돌아간다. 휴대폰 폭에서는 헤더의 작은 제목으로 대신한다. */
export function Signboard({ onHome }: { onHome: () => void }) {
  return (
    <div className="sign-board hidden border-b border-panel-line/70 sm:block">
      <div className="mx-auto flex max-w-5xl flex-col items-center px-4 py-8 sm:py-10">
        <div className="flex items-center gap-6 sm:gap-12">
          <span className="sign-line hidden translate-y-2 min-[840px]:block" aria-hidden />
          <button onClick={onHome} className="rounded-xl" aria-label="영양 편의점 메인으로">
            <span className="sign-title block whitespace-nowrap text-5xl font-black tracking-[0.14em] sm:text-7xl">
              영양 편의점
            </span>
          </button>
          <span className="sign-line hidden translate-y-2 min-[840px]:block" aria-hidden />
        </div>
        <p className="mt-3 whitespace-nowrap text-sm font-semibold tracking-wide text-slate-100 sm:text-xl">
          AI 맞춤 식단 &amp; 예산 매칭 서비스
        </p>
      </div>
    </div>
  );
}
