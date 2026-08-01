"use client";

import { useEffect, useState } from "react";
import type { Product } from "@/lib/api";
import { getRecent, pushRecent } from "@/lib/recentlyViewed";
import RailCard from "@/components/RailCard";

export default function RecentlyViewedRail({ product }: { product: Product }) {
  const [items, setItems] = useState<Product[]>([]);

  useEffect(() => {
    // Read recents BEFORE pushing the current product, so it never appears in its own rail.
    setItems(getRecent(product.id));
    pushRecent(product);
  }, [product]);

  if (items.length === 0) return null;

  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold mb-4">Recently viewed</h2>
      <div className="flex gap-4 overflow-x-auto snap-x scroll-pl-4 -mx-4 px-4 pb-2">
        {items.map((p) => (
          <RailCard key={p.id} product={p} />
        ))}
      </div>
    </section>
  );
}
