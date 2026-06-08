"use client";

import Link from "next/link";
import { useWishlist } from "@/lib/useWishlist";
import ProductCard from "@/components/ProductCard";

export default function WishlistPage() {
  const { items } = useWishlist();

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Wishlist</h1>
      {items.length === 0 ? (
        <div className="text-center py-16 border border-dashed rounded-lg">
          <p className="text-zinc-500">Your wishlist is empty.</p>
          <Link href="/" className="inline-block mt-4 text-sm underline">
            Continue shopping
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
