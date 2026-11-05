import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useReturnFocus } from "@/hooks/useReturnFocus";
import { cn } from "@/utils/cn";

export interface ReviewTarget {
  barcodes: string[];
  names: string[];
  initialRating?: number;
  initialComment?: string;
}

interface Props {
  target: ReviewTarget | null;
  onClose: () => void;
  onSubmit: (target: ReviewTarget, rating: number, comment: string) => Promise<void>;
}

export function ReviewDialog({ target, onClose, onSubmit }: Props) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onCloseAutoFocus = useReturnFocus(Boolean(target));

  useEffect(() => {
    if (!target) return;
    setRating(target.initialRating ?? 0);
    setComment(target.initialComment ?? "");
    setError(null);
  }, [target]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!target || !rating) return;
    setSaving(true);
    setError(null);
    try {
      await onSubmit(target, rating, comment.trim());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "저장하지 못했어요.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={Boolean(target)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent onCloseAutoFocus={onCloseAutoFocus}>
        <DialogTitle className="text-xl font-bold tracking-[-0.02em]">이 구성 어땠어요?</DialogTitle>
        <DialogDescription className="mt-1 text-sm text-muted">{target?.names.join(" + ")}</DialogDescription>
        <form onSubmit={submit} className="mt-4 grid gap-4">
          <fieldset>
            <legend className="mb-2 font-mono text-xs tracking-[0.06em] text-muted">별점</legend>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-label={`별점 ${value}점`}
                  aria-pressed={rating === value}
                  onClick={() => setRating(value)}
                  className={cn(
                    "h-10 w-10 rounded-btn border font-mono text-lg",
                    value <= rating ? "border-lime bg-lime text-lime-ink" : "border-line text-muted hover:border-muted",
                  )}
                >
                  ★
                </button>
              ))}
            </div>
          </fieldset>
          <label className="grid gap-2">
            <span className="flex justify-between font-mono text-xs tracking-[0.06em] text-muted">
              한 줄 리뷰
              <span className="tnum">{comment.length}/200</span>
            </span>
            <input
              value={comment}
              maxLength={200}
              onChange={(event) => setComment(event.target.value)}
              placeholder="예: 운동 끝나고 먹기 딱 좋았어요"
              className="rounded-btn border border-line bg-panel-2 px-3 py-3 text-base outline-none focus:border-lime"
            />
          </label>
          {error && <p role="alert" className="text-sm text-alert">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>
              닫기
            </Button>
            <Button variant="lime" type="submit" disabled={!rating || saving}>
              {saving ? "저장 중" : "리뷰 남기기"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
