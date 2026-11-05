import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Check, Sparkles, Star } from "lucide-react";
import { fetchReviews, postReview } from "@/api/client";
import type { Parsed, SavedReview } from "@/api/types";
import { getSessionId } from "@/utils/storage";

export interface ReviewTarget {
  key: string;
  label: string;
  barcodes: string[];
  queryText: string | null;
  parsed: Parsed | null;
}

interface Props {
  targets: ReviewTarget[];
  onHome: () => void;
  onNotice: (message: string) => void;
}

interface RankRow {
  key: string;
  title: string;
  average: number;
  count: number;
  comment: string | null;
}

/** 같은 조합의 리뷰를 묶어 평균이 높은 순으로 줄 세운다. 서버는 최신순으로 준다. */
function buildRanking(reviews: SavedReview[]): RankRow[] {
  const groups = new Map<string, SavedReview[]>();
  reviews.forEach((review) => groups.set(review.combo_key, [...(groups.get(review.combo_key) ?? []), review]));
  return [...groups.entries()]
    .map(([key, group]) => ({
      key,
      title: group[0].items.map((item) => item.product_name ?? "판매 종료 상품").join(" + "),
      average: group.reduce((sum, review) => sum + review.rating, 0) / group.length,
      count: group.length,
      comment: group.find((review) => review.comment)?.comment ?? null,
    }))
    .sort((a, b) => b.average - a.average || b.count - a.count);
}

export function RatingsPage({ targets, onHome, onNotice }: Props) {
  const [reviews, setReviews] = useState<SavedReview[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [targetKey, setTargetKey] = useState("");
  const [stars, setStars] = useState(5);
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const target = targets.find((item) => item.key === targetKey) ?? targets[0];

  const load = useCallback(() => {
    setLoadError(null);
    return fetchReviews().then(
      (data) => setReviews(data.items),
      (error: Error) => setLoadError(error.message),
    );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!target || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      await postReview({
        barcodes: target.barcodes,
        rating: stars,
        comment: comment.trim(),
        query_text: target.queryText,
        parsed_json: target.parsed,
        session_id: getSessionId(),
      });
      setComment("");
      setStars(5);
      onNotice("별점 평가가 저장되었습니다!");
      await load();
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "저장하지 못했어요.");
    } finally {
      setSaving(false);
    }
  };

  const ranking = reviews ? buildRanking(reviews) : [];

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/60 p-6 sm:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-black text-white">
            <Star className="h-6 w-6 fill-amber-400 text-amber-400" />
            추천 메뉴 사용자 별점 랭킹
          </h2>
          <p className="mt-1 text-sm text-slate-400">사용자들이 남긴 별점의 평균이 높은 순서입니다.</p>
        </div>
        <button onClick={onHome} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700">
          메인 추천으로 돌아가기
        </button>
      </div>

      <form onSubmit={submit} className="mb-8 space-y-3 rounded-2xl border border-slate-800 bg-slate-950/70 p-5">
        <h3 className="flex items-center gap-1.5 text-sm font-bold text-emerald-400">
          <Sparkles className="h-4 w-4" />
          선택한 조합에 별점 평가 남기기
        </h3>
        {!target ? (
          <p className="text-sm text-slate-400">추천을 받거나 장바구니에 담으면 그 조합에 별점을 남길 수 있어요.</p>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="min-w-0">
                <label htmlFor="review-target" className="mb-1 block text-xs text-slate-400">평가할 조합 선택</label>
                <select
                  id="review-target"
                  value={target.key}
                  onChange={(event) => setTargetKey(event.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                >
                  {targets.map((item) => (
                    <option key={item.key} value={item.key}>{item.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <span className="mb-1 block text-xs text-slate-400">별점 부여</span>
                <div className="flex h-9 items-center gap-1">
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button
                      key={value}
                      type="button"
                      aria-label={`${value}점`}
                      aria-pressed={stars === value}
                      onClick={() => setStars(value)}
                      className="p-1 transition-transform hover:scale-110"
                    >
                      <Star className={`h-5 w-5 ${value <= stars ? "fill-amber-400 text-amber-400" : "text-slate-600"}`} />
                    </button>
                  ))}
                  <span className="ml-2 text-xs font-bold text-amber-400">{stars}점</span>
                </div>
              </div>
            </div>
            <input
              type="text"
              aria-label="한줄평 (선택)"
              placeholder="한줄평을 적어 주세요 (선택)"
              value={comment}
              maxLength={200}
              onChange={(event) => setComment(event.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white placeholder-slate-500"
            />
            {saveError && <p role="alert" className="text-xs font-semibold text-rose-300">{saveError}</p>}
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] text-slate-500">같은 조합에 다시 남기면 이전 평가를 고칩니다.</p>
              <button
                type="submit"
                disabled={saving}
                className="flex shrink-0 items-center gap-1.5 rounded-xl bg-emerald-400 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-emerald-300 disabled:opacity-50"
              >
                <Check className="h-3.5 w-3.5 stroke-[3]" />
                {saving ? "저장 중…" : "평가 등록하기"}
              </button>
            </div>
          </>
        )}
      </form>

      {loadError ? (
        <p role="alert" className="text-sm font-semibold text-rose-300">{loadError}</p>
      ) : reviews === null ? (
        <p className="text-sm text-slate-400">불러오는 중…</p>
      ) : ranking.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-400">아직 등록된 별점이 없어요. 첫 평가를 남겨 보세요.</p>
      ) : (
        <ol className="space-y-3">
          {ranking.map((row, index) => (
            <li key={row.key} className="flex items-start justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900 p-4">
              <div className="min-w-0">
                <span className="text-sm font-bold text-white">{row.title}</span>
                <div className="mt-1 flex items-center gap-2">
                  <span className="flex items-center text-amber-400">
                    <Star className="h-3.5 w-3.5 fill-amber-400" />
                    <span className="ml-1 text-xs font-black">{row.average.toFixed(1)}</span>
                  </span>
                  <span className="text-[11px] text-slate-500">평가 {row.count}개</span>
                </div>
                {row.comment && <p className="mt-1 text-xs text-slate-300">{row.comment}</p>}
              </div>
              <span className="shrink-0 rounded border border-emerald-800/40 bg-emerald-950 px-2 py-1 text-xs font-bold text-emerald-400">
                #{index + 1}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
