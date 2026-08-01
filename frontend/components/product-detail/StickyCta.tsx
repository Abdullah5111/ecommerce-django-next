"use client";

import { useState } from "react";
import type { Product } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useToast } from "@/lib/useToast";
import Price from "@/components/ui/Price";

export default function StickyCta({ product }: { product: Product }) {
  const [qty, setQty] = useState(1);
  const { add } = useCart();
  const { toast } = useToast();
  const hasVariants = (product.variants?.length ?? 0) > 0;
  const maxQty = Math.max(1, product.stock);
  const outOfStock = !hasVariants && product.stock === 0;

  const dec = () => setQty((q) => Math.max(1, q - 1));
  const inc = () => setQty((q) => Math.min(maxQty, q + 1));

  const handleAdd = () => {
    // Variant products can't be added from the compact bar — scroll up to the buy box.
    if (hasVariants) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    add(product, null, qty);
    toast("Added to cart", "success");
  };

  return (
    <div className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white border-t border-zinc-200 shadow-[0_-4px_12px_rgba(0,0,0,0.05)] px-4 py-3 flex items-center gap-3">
      <Price
        price={hasVariants ? (product.price_from ?? product.price) : product.price}
        compareAt={hasVariants ? null : product.compare_at_price}
        size="sm"
        showPercent={false}
      />

      {!outOfStock && !hasVariants && (
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
        className="flex-1 bg-brand text-brand-fg px-4 py-2.5 rounded-lg font-medium hover:bg-brand-dark disabled:bg-zinc-300"
      >
        {outOfStock ? "Out of stock" : hasVariants ? "Choose options" : "Add to cart"}
      </button>
    </div>
  );
}
