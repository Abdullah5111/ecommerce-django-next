"use client";

import { useWishlist } from "@/lib/useWishlist";
import ProductCard from "@/components/ProductCard";
import EmptyState from "@/components/EmptyState";

export default function WishlistPage() {
  const { items } = useWishlist();

  if (items.length === 0) {
    return (
      <EmptyState
        icon={
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 1 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78z" /></svg>
        }
        title="Your wishlist is empty"
        message="Tap the heart on any product to save it here for later."
        ctaHref="/"
        ctaLabel="Browse products"
      />
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Wishlist</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}
      </div>
    </div>
  );
}
