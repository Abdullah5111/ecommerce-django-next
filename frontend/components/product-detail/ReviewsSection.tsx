import type { Review } from "@/lib/api";
import Badge from "@/components/ui/Badge";
import RatingStars from "@/components/RatingStars";
import HelpfulButton from "./HelpfulButton";
import ReviewCta from "./ReviewCta";
import ReviewPhotos from "./ReviewPhotos";
import ReviewViewerState from "./ReviewViewerState";

type Props = {
  slug: string;
  reviews: Review[];
  count: number;
  ratingAvg: string;
  ratingCount: number;
};

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function StarRow({ rating }: { rating: number }) {
  return (
    <div className="inline-flex">
      {[1, 2, 3, 4, 5].map((n) => (
        <svg key={n} width="14" height="14" viewBox="0 0 20 20" aria-hidden="true">
          <path
            d="M10 1.5l2.6 5.3 5.9.86-4.25 4.14 1 5.85L10 14.9 4.75 17.65l1-5.85L1.5 7.66l5.9-.86L10 1.5z"
            fill={n <= rating ? "#facc15" : "#e4e4e7"}
          />
        </svg>
      ))}
    </div>
  );
}

export default function ReviewsSection({
  slug,
  reviews,
  count,
  ratingAvg,
  ratingCount,
}: Props) {
  const avgNumeric = parseFloat(ratingAvg);
  const safeAvg = isNaN(avgNumeric) ? 0 : avgNumeric;

  const histogram: { star: number; n: number; pct: number }[] = [5, 4, 3, 2, 1].map((s) => {
    const n = reviews.filter((r) => r.rating === s).length;
    const pct = reviews.length > 0 ? Math.round((n / reviews.length) * 100) : 0;
    return { star: s, n, pct };
  });

  return (
    <div>
      <div className="flex flex-col md:flex-row gap-8 md:items-start">
        <div className="md:w-64 shrink-0">
          <div className="text-5xl font-bold leading-none">{safeAvg.toFixed(1)}</div>
          <div className="mt-2">
            {ratingCount > 0 ? (
              <RatingStars value={ratingAvg} count={ratingCount} size="md" />
            ) : (
              <div className="text-sm text-zinc-500">No reviews yet</div>
            )}
          </div>
          <div className="text-sm text-zinc-500 mt-1">
            ({count} review{count === 1 ? "" : "s"})
          </div>
        </div>

        {reviews.length > 0 && (
          <div className="flex-1 space-y-1.5">
            {histogram.map((h) => (
              <div key={h.star} className="flex items-center gap-2 text-xs text-zinc-600">
                <span className="w-6 text-right">{h.star}★</span>
                <div className="flex-1 h-2 bg-zinc-100 rounded overflow-hidden">
                  <div
                    className="h-full bg-amber-400"
                    style={{ width: `${h.pct}%` }}
                  />
                </div>
                <span className="w-8 text-right tabular-nums">{h.n}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-8">
        <ReviewCta slug={slug} />
      </div>

      {reviews.length > 0 ? (
        // List stays server-rendered (SEO); the provider resolves the per-viewer bits in one request.
        <ReviewViewerState slug={slug}>
          <ul className="mt-8 space-y-6">
            {reviews.map((r) => (
              <li key={r.id} className="border-b pb-6 last:border-0">
                <StarRow rating={r.rating} />
                {r.title && <div className="font-semibold mt-1">{r.title}</div>}
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-zinc-500 mt-1">
                  <span>
                    {r.author_name} · {fmtDate(r.created_at)}
                  </span>
                  {r.verified_purchase && (
                    <Badge tone="success" className="normal-case tracking-normal">
                      ✓ Verified purchase
                    </Badge>
                  )}
                </div>
                {r.body && (
                  <p className="text-sm text-zinc-700 mt-2 whitespace-pre-line leading-relaxed">
                    {r.body}
                  </p>
                )}
                {r.images.length > 0 && <ReviewPhotos images={r.images} />}
                <div className="mt-3">
                  <HelpfulButton reviewId={r.id} initialCount={r.helpful_count} />
                </div>
              </li>
            ))}
          </ul>
        </ReviewViewerState>
      ) : (
        <p className="mt-8 text-sm text-zinc-500">
          Be the first to review this product.
        </p>
      )}
    </div>
  );
}
