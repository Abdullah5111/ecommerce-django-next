import { FREE_SHIPPING_THRESHOLD } from "@/lib/constants";

const ITEMS = [
  `Free shipping over $${FREE_SHIPPING_THRESHOLD}`,
  "30-day free returns",
  "Secure checkout",
];

/** Thin trust/value-prop bar above the header. */
export default function TopBar() {
  return (
    <div className="bg-ink text-zinc-300 text-xs">
      <div className="max-w-6xl mx-auto px-4 h-9 flex items-center justify-center gap-2 sm:gap-6">
        {ITEMS.map((item, i) => (
          <span
            key={item}
            className={i > 0 ? "hidden sm:inline-flex items-center gap-2" : "inline-flex items-center gap-2"}
          >
            {i > 0 && <span className="text-zinc-600" aria-hidden>·</span>}
            <span>{item}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
