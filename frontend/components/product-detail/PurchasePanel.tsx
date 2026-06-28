"use client";

import { useState } from "react";
import type { Product } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useToast } from "@/lib/useToast";
import { useWishlist } from "@/lib/useWishlist";
import RatingStars from "@/components/RatingStars";
import { formatSold } from "@/lib/format";

function HeartIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill={filled ? "#dc2626" : "none"}
      stroke={filled ? "#dc2626" : "currentColor"}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  );
}

export default function PurchasePanel({ product }: { product: Product }) {
  const [qty, setQty] = useState(1);
  const { add } = useCart();
  const { toast } = useToast();
  const { has, toggle } = useWishlist();

  const inWishlist = has(product.id);
  const maxQty = Math.max(1, product.stock);
  const dec = () => setQty((q) => Math.max(1, q - 1));
  const inc = () => setQty((q) => Math.min(maxQty, q + 1));

  const handleAdd = () => {
    add(product, qty);
    toast("Added to cart", "success");
  };

  const handleWishlist = () => {
    toggle(product);
    toast(inWishlist ? "Removed from wishlist" : "Added to wishlist", "success");
  };

  let stockMessage: React.ReactNode = null;
  if (product.stock > 0 && product.stock < 5) {
    stockMessage = (
      <div className="text-sm text-red-600 mt-3 font-medium">
        Only {product.stock} left — order soon
      </div>
    );
  } else if (product.stock >= 5 && product.stock < 10) {
    stockMessage = (
      <div className="text-sm text-amber-700 mt-3 font-medium">
        Selling fast — {product.stock} in stock
      </div>
    );
  }

  return (
    <div>
      <div className="text-sm text-zinc-500 uppercase">{product.category.name}</div>
      <h1 className="text-3xl font-bold mt-1">{product.name}</h1>

      {product.rating_count > 0 && (
        <div className="mt-2">
          <RatingStars value={product.rating_avg} count={product.rating_count} size="md" />
        </div>
      )}

      {typeof product.sold_count === "number" && product.sold_count > 0 && (
        <div className="mt-1 text-sm text-zinc-500">
          {formatSold(product.sold_count)} sold
        </div>
      )}

      <div className="mt-4 flex items-center gap-4">
        <div className="text-2xl font-semibold flex items-baseline gap-3">
          {product.is_on_sale && product.compare_at_price ? (
            <>
              <span className="text-red-600">${product.price}</span>
              <span className="text-base text-zinc-400 line-through font-normal">
                ${product.compare_at_price}
              </span>
              {product.discount_percent > 0 && (
                <span className="text-sm bg-red-600 text-white px-2 py-0.5 rounded font-medium">
                  -{product.discount_percent}%
                </span>
              )}
            </>
          ) : (
            <span>${product.price}</span>
          )}
        </div>
        <button
          type="button"
          onClick={handleWishlist}
          aria-label={inWishlist ? "Remove from wishlist" : "Add to wishlist"}
          aria-pressed={inWishlist}
          className="ml-auto w-10 h-10 rounded-full border border-zinc-300 hover:bg-zinc-50 flex items-center justify-center"
        >
          <HeartIcon filled={inWishlist} />
        </button>
      </div>

      <p className="text-zinc-700 mt-4 leading-relaxed whitespace-pre-line">
        {product.description}
      </p>

      {stockMessage}

      {product.stock > 0 && (
        <div className="mt-6 flex items-center gap-3">
          <div className="inline-flex items-center border rounded">
            <button
              type="button"
              onClick={dec}
              disabled={qty <= 1}
              className="px-3 py-2 disabled:text-zinc-300 hover:bg-zinc-50"
              aria-label="Decrease quantity"
            >
              -
            </button>
            <span className="px-4 py-2 min-w-[2rem] text-center select-none">{qty}</span>
            <button
              type="button"
              onClick={inc}
              disabled={qty >= maxQty}
              className="px-3 py-2 disabled:text-zinc-300 hover:bg-zinc-50"
              aria-label="Increase quantity"
            >
              +
            </button>
          </div>
        </div>
      )}

      <button
        onClick={handleAdd}
        className="mt-6 bg-black text-white px-6 py-3 rounded font-medium hover:bg-zinc-800 disabled:bg-zinc-300 disabled:cursor-not-allowed"
        disabled={product.stock === 0}
      >
        {product.stock > 0 ? "Add to cart" : "Out of stock"}
      </button>
    </div>
  );
}
