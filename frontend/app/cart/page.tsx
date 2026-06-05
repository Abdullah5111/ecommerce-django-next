"use client";

import Image from "next/image";
import Link from "next/link";
import { useCart } from "@/lib/cart";

export default function CartPage() {
  const { items, update, remove, total } = useCart();

  if (items.length === 0) {
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
      <div className="md:col-span-2 space-y-4">
        {items.map(({ product, quantity }) => (
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
                <button onClick={() => remove(product.id)} className="ml-4 text-sm text-red-600">Remove</button>
              </div>
            </div>
            <div className="font-semibold">${(parseFloat(product.price) * quantity).toFixed(2)}</div>
          </div>
        ))}
      </div>
      <aside className="bg-white p-6 rounded border h-fit">
        <div className="flex justify-between mb-4">
          <span>Subtotal</span>
          <span className="font-semibold">${total.toFixed(2)}</span>
        </div>
        <Link href="/checkout" className="block text-center bg-black text-white py-3 rounded font-medium hover:bg-zinc-800">
          Checkout
        </Link>
      </aside>
    </div>
  );
}
