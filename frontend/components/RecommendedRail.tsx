"use client";

import { useEffect, useState } from "react";
import { api, type Product } from "@/lib/api";
import { auth } from "@/lib/auth";
import RailCard from "./RailCard";

/** Personalized "Recommended for you" rail; logged-in users only (guests see Featured). */
export default function RecommendedRail() {
  const [items, setItems] = useState<Product[]>([]);

  useEffect(() => {
    const token = auth.get();
    if (!token) return; // guests: skip (no personalization)
    api
      .getRecommended(token)
      .then(setItems)
      .catch(() => setItems([]));
  }, []);

  if (items.length === 0) return null;

  return (
    <section className="mb-8">
      <h2 className="text-xl font-semibold mb-3">Recommended for you</h2>
      <div className="flex overflow-x-auto snap-x snap-mandatory gap-4 pb-2 -mx-4 px-4">
        {items.map((p) => (
          <RailCard key={p.id} product={p} />
        ))}
      </div>
    </section>
  );
}
