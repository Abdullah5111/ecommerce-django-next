"use client";

import Image from "next/image";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { useWishlist } from "@/lib/useWishlist";
import type { Product } from "@/lib/api";

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
      <div className="text-center py-20">
        <h2 className="text-2xl font-semibold">Your cart is empty</h2>
        <Link href="/" className="text-blue-600 underline mt-4 inline-block">
          Continue shopping
        </Link>
      </div>
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
        <aside className="bg-white p-6 rounded border h-fit">
          <div className="flex justify-between mb-4">
            <span>Subtotal</span>
            <span className="font-semibold">${total.toFixed(2)}</span>
          </div>
          <Link href="/checkout" className="block text-center bg-black text-white py-3 rounded font-medium hover:bg-zinc-800">
            Checkout
          </Link>
        </aside>
      )}
    </div>
  );
}
