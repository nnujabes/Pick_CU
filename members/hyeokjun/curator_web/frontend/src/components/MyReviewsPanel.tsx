import { useEffect, useState } from "react";
import { fetchReviews } from "@/api/client";
import type { SavedReview } from "@/api/types";
import { Button } from "@/components/ui/button";
import { getSessionId } from "@/utils/storage";
import { SidePanel } from "./SidePanel";

interface Props {
  open: boolean;
  /** 리뷰를 저장하면 값이 바뀌어 목록을 다시 불러온다. */
  version: number;
  onClose: () => void;
  onEdit: (review: SavedReview) => void;
}

export function MyReviewsPanel({ open, version, onClose, onEdit }: Props) {
  const [reviews, setReviews] = useState<SavedReview[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setError(null);
    fetchReviews({ session_id: getSessionId(), limit: 100 }, controller.signal)
      .then((body) => setReviews(body.items))
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "리뷰를 불러오지 못했어요.");
      });
    return () => controller.abort();
  }, [open, version]);

  return (
    <SidePanel open={open} title="내 리뷰" meta={reviews ? `${reviews.length}개` : undefined} onClose={onClose}>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6">
        {error && <p role="alert" className="py-4 text-sm text-alert">{error}</p>}
        {!error && reviews && !reviews.length && (
          <p className="py-6 text-sm text-muted">이 브라우저에서 쓴 리뷰가 아직 없어요.</p>
        )}
        <ul>
          {reviews?.map((review) => (
            <li key={review.id} className="grid gap-2 border-b border-line py-3">
              <p className="text-[15px] font-medium leading-snug">
                {review.items.map((item) => item.product_name ?? "판매가 끝난 상품").join(" + ")}
              </p>
              <p className="text-sm">
                <span className="tnum mr-2 font-mono text-lime">★ {review.rating}</span>
                {review.comment || <span className="text-muted">한 줄 리뷰 없음</span>}
              </p>
              <div className="flex items-center justify-between gap-2">
                <span className="tnum font-mono text-xs text-dim">
                  {(review.updated_at ?? review.created_at).slice(0, 10)}
                  {review.updated_at ? " 수정" : ""}
                </span>
                <Button size="sm" aria-label={`${review.items[0]?.product_name ?? "상품"} 리뷰 고치기`} onClick={() => onEdit(review)}>
                  고치기
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </SidePanel>
  );
}
