import { useState } from "react";
import type { Category } from "@/api/types";
import { cn } from "@/utils/cn";

const CATEGORY_LOOK: Record<Category, { background: string; path: string }> = {
  간편식사: { background: "#5f9d90", path: "M4 9h16v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9Zm1-4h14l1 4H4l1-4Z" },
  즉석조리: { background: "#b9834f", path: "M12 3c2 3-1 4 0 6s3 2 3 5a3 3 0 0 1-6 0c0-2-2-3 0-6 1-2 3-2 3-5ZM5 19h14v2H5v-2Z" },
  과자류: { background: "#e4834b", path: "M7 3h10l-1 3 1 3-1 3 1 3-1 3 1 3H7l1-3-1-3 1-3-1-3 1-3-1-3Z" },
  아이스크림: { background: "#6fa9c4", path: "M8 3h8v12H8V3Zm3 12h2v6h-2v-6Z" },
  식품: { background: "#c49c62", path: "M6 8h12l-2 13H8L6 8Zm-1-4h14v3H5V4Z" },
  음료: { background: "#35523f", path: "M10 2h4v4l3 4v10a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V10l3-4V2Z" },
};

/** 한 번 실패한 주소는 다시 요청하지 않는다. */
const failedUrls = new Set<string>();

function toHttps(url: string | null | undefined) {
  if (!url) return null;
  const trimmed = url.trim();
  if (!trimmed) return null;
  return trimmed.replace(/^http:\/\//i, "https://");
}

function FallbackImage({ category, compact }: { category: Category; compact: boolean }) {
  const look = CATEGORY_LOOK[category];
  return (
    <div className="flex h-full w-full items-center justify-center" style={{ background: look.background }} data-image-fallback>
      <svg viewBox="0 0 24 24" className={compact ? "h-5 w-5" : "h-10 w-10"} fill="#f1f2ec" aria-hidden>
        <path d={look.path} />
      </svg>
    </div>
  );
}

interface Props {
  url: string | null | undefined;
  category: Category;
  alt: string;
  compact?: boolean;
  className?: string;
}

/** 틀 크기는 부모가 정한다. 사진이 깨져도 레이아웃은 그대로다. */
export function ProductImage({ url, category, alt, compact = false, className }: Props) {
  const source = toHttps(url);
  const [failed, setFailed] = useState(false);
  const showFallback = !source || failed || failedUrls.has(source);
  return (
    <div className={cn("h-full w-full overflow-hidden bg-white", className)}>
      {showFallback ? (
        <FallbackImage category={category} compact={compact} />
      ) : (
        <img
          src={source}
          alt={alt}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="h-full w-full object-contain"
          onError={() => {
            failedUrls.add(source);
            setFailed(true);
          }}
        />
      )}
    </div>
  );
}
