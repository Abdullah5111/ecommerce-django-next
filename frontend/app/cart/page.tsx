"use client";

import Image from "next/image";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { useWishlist } from "@/lib/useWishlist";
import type { Product } from "@/lib/api";
import FreeShippingBar from "@/components/FreeShippingBar";
import EmptyState from "@/components/EmptyState";

export default function CartPage() {
  const { items, add, update, remove, total } = useCart();
  const { items: saved, has, toggle } = useWishlist();

  // "Save for later" reuses the wishlist as its store: move the line into the
  // wishlist (if not already there) and drop it from the cart.
  const saveForLater = (product: Product) => {
    if (!has(product.id)) toggle(product);
    remove(product.id);
  };

  // "Move to cart" is the reverse: add to the cart and remove from the wishlist.
  const moveToCart = (product: Product) => {
    add(product, 1);
    if (has(product.id)) toggle(product);
  };

  if (items.length === 0 && saved.length === 0) {
    return (
      <EmptyState
        icon={
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 6h15l-1.5 9h-12zM6 6L5 3H2M9 20a1 1 0 1 0 0 .01M18 20a1 1 0 1 0 0 .01" /></svg>
        }
        title="Your cart is empty"
        message="Browse the catalog and add something you love — free shipping over $50."
        ctaHref="/"
        ctaLabel="Start shopping"
      />
    );
  }

  return (
    <div className="grid md:grid-cols-3 gap-8">
      <div className="md:col-span-2 space-y-8">
        <section className="space-y-4">
          {items.length === 0 ? (
            <p className="text-zinc-500 bg-white p-4 rounded border">
              Your cart is empty — move a saved item back below, or{" "}
              <Link href="/" className="underline">
                keep shopping
              </Link>
              .
            </p>
          ) : (
            items.map(({ product, quantity }) => (
              <div key={product.id} className="flex gap-4 bg-white p-4 rounded border">
                <div className="relative w-24 h-24 bg-zinc-100 rounded overflow-hidden shrink-0">
                  {product.image_url && (
                    <Image
                      src={product.image_url}
                      alt={product.name}
                      fill
                      sizes="96px"
                      className="object-cover"
                    />
                  )}
                </div>
                <div className="flex-1">
                  <div className="font-medium">{product.name}</div>
                  <div className="text-sm text-zinc-500">${product.price} each</div>
                  <div className="mt-2 flex items-center gap-2">
                    <button onClick={() => update(product.id, quantity - 1)} className="px-2 border rounded">-</button>
                    <span>{quantity}</span>
                    <button onClick={() => update(product.id, quantity + 1)} className="px-2 border rounded">+</button>
                    <button onClick={() => saveForLater(product)} className="ml-4 text-sm text-blue-600 hover:underline">
                      Save for later
                    </button>
                    <button onClick={() => remove(product.id)} className="text-sm text-red-600 hover:underline">Remove</button>
                  </div>
                </div>
                <div className="font-semibold">${(parseFloat(product.price) * quantity).toFixed(2)}</div>
              </div>
            ))
          )}
        </section>

        {saved.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-3">
              Saved for later <span className="text-zinc-400 font-normal">({saved.length})</span>
            </h2>
            <div className="space-y-3">
              {saved.map((product) => (
                <div key={product.id} className="flex gap-4 bg-white p-4 rounded border">
                  <div className="relative w-20 h-20 bg-zinc-100 rounded overflow-hidden shrink-0">
                    {product.image_url && (
                      <Image
                        src={product.image_url}
                        alt={product.name}
                        fill
                        sizes="80px"
                        className="object-cover"
                      />
                    )}
                  </div>
                  <div className="flex-1">
                    <Link href={`/products/${product.id}`} className="font-medium hover:underline">
                      {product.name}
                    </Link>
                    <div className="text-sm text-zinc-500">${product.price}</div>
                    <div className="mt-2 flex items-center gap-3">
                      <button
                        onClick={() => moveToCart(product)}
                        disabled={product.stock <= 0}
                        className="text-sm text-blue-600 hover:underline disabled:text-zinc-400 disabled:no-underline"
                      >
                        {product.stock <= 0 ? "Out of stock" : "Move to cart"}
                      </button>
                      <button onClick={() => toggle(product)} className="text-sm text-red-600 hover:underline">
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      {items.length > 0 && (
        <aside className="bg-white p-6 rounded-card border border-zinc-200 shadow-card h-fit md:sticky md:top-4">
          <FreeShippingBar subtotal={total} />
          <div className="flex justify-between mb-4 pt-4 border-t border-zinc-100">
            <span>Subtotal</span>
            <span className="font-semibold tabular-nums">${total.toFixed(2)}</span>
          </div>
          <Link
            href="/checkout"
            className="block text-center bg-brand text-brand-fg py-3 rounded-lg font-medium hover:bg-brand-dark transition-colors"
          >
            Checkout
          </Link>
        </aside>
      )}
    </div>
  );
}
