import { FREE_SHIPPING_THRESHOLD } from "@/lib/constants";
import { cn } from "@/lib/cn";

/** Progress toward the free-shipping threshold — a small conversion nudge. */
export default function FreeShippingBar({ subtotal }: { subtotal: number }) {
  const remaining = Math.max(0, FREE_SHIPPING_THRESHOLD - subtotal);
  const pct = Math.min(100, (subtotal / FREE_SHIPPING_THRESHOLD) * 100);
  const unlocked = remaining <= 0;

  return (
    <div className="mb-4">
      <p className="text-sm mb-2">
        {unlocked ? (
          <span className="font-medium text-success">✓ You’ve unlocked free shipping</span>
        ) : (
          <>
            Add <span className="font-semibold text-deal-dark">${remaining.toFixed(2)}</span> more for
            free shipping
          </>
        )}
      </p>
      <div
        className="h-2 rounded-full bg-zinc-200 overflow-hidden"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={FREE_SHIPPING_THRESHOLD}
        aria-valuenow={Math.min(subtotal, FREE_SHIPPING_THRESHOLD)}
      >
        <div
          className={cn("h-full rounded-full transition-all duration-500", unlocked ? "bg-success" : "bg-deal")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
