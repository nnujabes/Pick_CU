import { useState } from "react";
import { ShoppingBag } from "lucide-react";

const toHttps = (url: string | null) => url?.trim().replace(/^http:\/\//i, "https://") || null;

/** 틀 크기는 부모가 정한다. 사진이 없거나 깨져도 레이아웃은 그대로다. */
export function ProductImage({ url, alt }: { url: string | null; alt: string }) {
  const source = toHttps(url);
  const [failed, setFailed] = useState(false);
  if (!source || failed) {
    return (
      <div className="flex h-full w-full items-center justify-center rounded-lg bg-slate-700" data-image-fallback>
        <ShoppingBag className="h-6 w-6 text-slate-400" aria-hidden />
      </div>
    );
  }
  return (
    <img
      src={source}
      alt={alt}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className="h-full w-full rounded-lg bg-white object-contain"
    />
  );
}
