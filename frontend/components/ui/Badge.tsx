import { cn } from "@/lib/cn";

export type BadgeTone = "brand" | "deal" | "success" | "warning" | "danger" | "neutral";

// Soft (tinted bg + colored text) is the default; `solid` fills for emphasis
// like a %-off flag.
const soft: Record<BadgeTone, string> = {
  brand: "bg-brand-light text-brand",
  deal: "bg-deal-light text-deal-dark",
  success: "bg-emerald-50 text-success",
  warning: "bg-amber-50 text-deal-dark",
  danger: "bg-rose-50 text-danger",
  neutral: "bg-zinc-100 text-zinc-600",
};

const solid: Record<BadgeTone, string> = {
  brand: "bg-brand text-brand-fg",
  deal: "bg-deal-dark text-white",
  success: "bg-success text-white",
  warning: "bg-warning text-white",
  danger: "bg-danger text-white",
  neutral: "bg-zinc-900 text-white",
};

export default function Badge({
  tone = "neutral",
  solid: isSolid = false,
  className,
  children,
}: {
  tone?: BadgeTone;
  solid?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        (isSolid ? solid : soft)[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
