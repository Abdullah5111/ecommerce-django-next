import type { Product } from "@/lib/api";
import RailCard from "@/components/RailCard";

export default function RelatedRail({
  products,
  categoryName,
}: {
  products: Product[];
  categoryName: string;
}) {
  if (!products || products.length === 0) return null;
  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold mb-4">More from {categoryName}</h2>
      <div className="flex gap-4 overflow-x-auto snap-x scroll-pl-4 -mx-4 px-4 pb-2">
        {products.map((p) => (
          <RailCard key={p.id} product={p} />
        ))}
      </div>
    </section>
  );
}
