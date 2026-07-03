import { cn } from "@/lib/cn";

type Money = string | number;

const SIZES = {
  sm: { now: "text-base", was: "text-xs", pct: "text-[10px]" },
  md: { now: "text-xl", was: "text-sm", pct: "text-xs" },
  lg: { now: "text-3xl", was: "text-base", pct: "text-sm" },
} as const;

function fmt(v: Money): string {
  return `$${Number(v).toFixed(2)}`;
}

/**
 * The store's price treatment — the one place that renders a current price with
 * an optional struck-through compare-at and a %-off flag. On sale the current
 * price uses the deal accent to pull the eye; otherwise it's plain ink.
 */
export default function Price({
  price,
  compareAt,
  size = "md",
  showPercent = true,
  className,
}: {
  price: Money;
  compareAt?: Money | null;
  size?: keyof typeof SIZES;
  showPercent?: boolean;
  className?: string;
}) {
  const now = Number(price);
  const was = compareAt == null ? null : Number(compareAt);
  const onSale = was != null && was > now;
  const pct = onSale ? Math.round((1 - now / was) * 100) : 0;
  const s = SIZES[size];

  return (
    <span className={cn("inline-flex items-baseline gap-2", className)}>
      <span className={cn("font-bold tabular-nums", s.now, onSale ? "text-deal-dark" : "text-ink")}>
        {fmt(now)}
      </span>
      {onSale && (
        <>
          <span className={cn("text-zinc-400 line-through tabular-nums", s.was)}>{fmt(was)}</span>
          {showPercent && (
            <span
              className={cn(
                "rounded bg-deal-dark px-1.5 py-0.5 font-semibold text-white",
                s.pct,
              )}
            >
              −{pct}%
            </span>
          )}
        </>
      )}
    </span>
  );
}
