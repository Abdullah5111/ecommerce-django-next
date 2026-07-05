import type { Product } from "@/lib/api";
import RailCard from "@/components/RailCard";
import CountdownTimer from "@/components/CountdownTimer";

/** "Deals of the day" — on-sale products with a lightning countdown. */
export default function DealsRail({ products }: { products: Product[] }) {
  if (products.length === 0) return null;
  return (
    <section className="mb-8">
      <div className="flex items-center justify-between gap-4 mb-3">
        <h2 className="text-xl font-semibold text-deal-dark">⚡ Deals of the day</h2>
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          <span className="hidden sm:inline">Ends in</span>
          <CountdownTimer />
        </div>
      </div>
      <div className="flex overflow-x-auto snap-x snap-mandatory gap-4 pb-2 -mx-4 px-4">
        {products.map((p) => (
          <RailCard key={p.id} product={p} />
        ))}
      </div>
    </section>
  );
}
