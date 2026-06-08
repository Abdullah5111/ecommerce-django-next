"use client";

import { useState } from "react";
import type { Product } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useToast } from "@/lib/useToast";

export default function StickyCta({ product }: { product: Product }) {
  const [qty, setQty] = useState(1);
  const { add } = useCart();
  const { toast } = useToast();
  const maxQty = Math.max(1, product.stock);
  const outOfStock = product.stock === 0;

  const dec = () => setQty((q) => Math.max(1, q - 1));
  const inc = () => setQty((q) => Math.min(maxQty, q + 1));

  const handleAdd = () => {
    add(product, qty);
    toast("Added to cart", "success");
  };

  return (
    <div className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white border-t border-zinc-200 shadow-[0_-4px_12px_rgba(0,0,0,0.05)] px-4 py-3 flex items-center gap-3">
      <div className="flex flex-col">
        {product.is_on_sale && product.compare_at_price ? (
          <>
            <span className="text-red-600 font-semibold leading-tight">${product.price}</span>
            <span className="text-xs text-zinc-400 line-through leading-tight">
              ${product.compare_at_price}
            </span>
          </>
        ) : (
          <span className="font-semibold">${product.price}</span>
        )}
      </div>
      {!outOfStock && (
        <div className="inline-flex items-center border rounded">
          <button
            type="button"
            onClick={dec}
            disabled={qty <= 1}
            className="px-2 py-1 disabled:text-zinc-300"
            aria-label="Decrease quantity"
          >
            -
          </button>
          <span className="px-2 min-w-[1.5rem] text-center text-sm select-none">{qty}</span>
          <button
            type="button"
            onClick={inc}
            disabled={qty >= maxQty}
            className="px-2 py-1 disabled:text-zinc-300"
            aria-label="Increase quantity"
          >
            +
          </button>
        </div>
      )}
      <button
        onClick={handleAdd}
        disabled={outOfStock}
        className="flex-1 bg-black text-white px-4 py-2.5 rounded font-medium disabled:bg-zinc-300"
      >
        {outOfStock ? "Out of stock" : "Add to cart"}
      </button>
    </div>
  );
}
