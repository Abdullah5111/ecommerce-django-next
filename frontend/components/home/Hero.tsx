import Link from "next/link";
import { buttonClasses } from "@/components/ui/Button";
import { FREE_SHIPPING_THRESHOLD } from "@/lib/constants";

/** Homepage hero — carries the page's single h1 in browse mode. */
export default function Hero() {
  return (
    <section className="relative overflow-hidden rounded-card bg-gradient-to-br from-brand to-brand-dark text-white p-8 md:p-12 mb-8">
      <div className="relative z-10 max-w-lg">
        <p className="text-xs font-semibold uppercase tracking-widest text-white/70">New season</p>
        <h1 className="mt-2 text-3xl md:text-4xl font-bold leading-tight">
          Everything you need, delivered fast.
        </h1>
        <p className="mt-3 text-white/85">
          Free shipping over ${FREE_SHIPPING_THRESHOLD} · 30-day returns · secure checkout.
        </p>
        <Link href="#catalog" className={buttonClasses("deal", "lg", "mt-6")}>
          Shop now
        </Link>
      </div>
      <div className="pointer-events-none absolute -right-16 -top-20 w-72 h-72 rounded-full bg-white/10" />
      <div className="pointer-events-none absolute right-6 bottom-0 w-40 h-40 rounded-full bg-deal/40 blur-3xl" />
    </section>
  );
}
