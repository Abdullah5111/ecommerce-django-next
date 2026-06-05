"use client";

import Link from "next/link";
import type { Product } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useToast } from "@/lib/useToast";
import RatingStars from "./RatingStars";

function Badge({ children, color }: { children: React.ReactNode; color: "red" | "green" | "amber" }) {
  const cls =
    color === "red"
      ? "bg-red-600 text-white"
      : color === "green"
        ? "bg-green-600 text-white"
        : "bg-amber-500 text-white";
  return (
    <span className={`${cls} text-[10px] font-semibold px-2 py-0.5 rounded uppercase tracking-wide`}>
      {children}
    </span>
  );
}

export default function ProductCard({ product }: { product: Product }) {
  const { add } = useCart();
  const { toast } = useToast();

  const firstImage = product.images?.[0]?.url || product.image_url;
  const secondImage = product.images?.[1]?.url;

  const badges: React.ReactNode[] = [];
  if (product.is_on_sale && product.discount_percent > 0) {
    badges.push(
      <Badge key="sale" color="red">
        −{product.discount_percent}% OFF
      </Badge>,
    );
  }
  if (product.created_at) {
    const created = new Date(product.created_at).getTime();
    const fourteenDays = 14 * 24 * 60 * 60 * 1000;
    if (!isNaN(created) && Date.now() - created < fourteenDays) {
      badges.push(
        <Badge key="new" color="green">
          New
        </Badge>,
      );
    }
  }
  if (product.stock > 0 && product.stock < 5) {
    badges.push(
      <Badge key="low" color="amber">
        Low stock
      </Badge>,
    );
  }
  const visibleBadges = badges.slice(0, 2);

  const handleAdd = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    add(product);
    toast("Added to cart", "success");
  };

  const outOfStock = product.stock === 0;

  return (
    <Link
      href={`/products/${product.slug}`}
      className="group block bg-white rounded-lg overflow-hidden border hover:shadow-md transition"
    >
      <div className="relative aspect-square overflow-hidden bg-zinc-100">
        {firstImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={firstImage}
            alt={product.name}
            className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${
              secondImage ? "group-hover:opacity-0" : "group-hover:scale-105"
            }`}
          />
        ) : null}
        {secondImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={secondImage}
            alt={product.name}
            className="absolute inset-0 w-full h-full object-cover opacity-0 group-hover:opacity-100 transition-opacity duration-300"
          />
        ) : null}

        {visibleBadges.length > 0 && (
          <div className="absolute top-2 left-2 flex flex-col gap-1 z-10">
            {visibleBadges}
          </div>
        )}

        <div className="absolute bottom-2 right-2 z-10">
          {outOfStock ? (
            <span className="bg-zinc-200 text-zinc-600 text-xs font-medium px-3 py-1.5 rounded-full">
              Out of stock
            </span>
          ) : (
            <button
              type="button"
              onClick={handleAdd}
              aria-label="Add to cart"
              className="w-9 h-9 rounded-full bg-black text-white flex items-center justify-center shadow-md hover:bg-zinc-800 transition opacity-0 group-hover:opacity-100 focus:opacity-100"
            >
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path
                  d="M10 4v12M4 10h12"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="p-4">
        <div className="text-xs text-zinc-500 uppercase tracking-wide">{product.category.name}</div>
        <h3 className="font-medium mt-1">{product.name}</h3>
        {product.rating_count > 0 && (
          <div className="mt-1">
            <RatingStars value={product.rating_avg} count={product.rating_count} />
          </div>
        )}
        <div className="mt-2 font-semibold flex items-baseline gap-2">
          {product.is_on_sale && product.compare_at_price ? (
            <>
              <span className="text-red-600">${product.price}</span>
              <span className="text-xs text-zinc-400 line-through font-normal">
                ${product.compare_at_price}
              </span>
            </>
          ) : (
            <span>${product.price}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
