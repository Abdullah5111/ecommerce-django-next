"use client";

import Image from "next/image";
import Link from "next/link";
import type { Product } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useWishlist } from "@/lib/useWishlist";
import { useToast } from "@/lib/useToast";
import { FREE_SHIPPING_THRESHOLD } from "@/lib/constants";
import { formatSold } from "@/lib/format";
import { cn } from "@/lib/cn";
import Badge from "@/components/ui/Badge";
import Price from "@/components/ui/Price";

export default function ProductCard({ product }: { product: Product }) {
  const { add } = useCart();
  const { has, toggle } = useWishlist();
  const { toast } = useToast();

  const firstImage = product.images?.[0]?.url || product.image_url;
  const secondImage = product.images?.[1]?.url;
  const outOfStock = product.stock === 0;
  const lowStock = product.stock > 0 && product.stock <= 5;
  const freeShip = Number(product.price) >= FREE_SHIPPING_THRESHOLD;
  const saved = has(product.id);
  const hasSold = typeof product.sold_count === "number" && product.sold_count > 0;

  // One corner flag, by priority: deal > new > featured. The price block already
  // carries the strikethrough, so the flag stays the single loud signal.
  const isNew =
    product.created_at &&
    Date.now() - new Date(product.created_at).getTime() < 14 * 24 * 60 * 60 * 1000;

  const handleAdd = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    add(product);
    toast("Added to cart", "success");
  };

  const handleWishlist = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggle(product);
  };

  return (
    <Link
      href={`/products/${product.slug}`}
      className="group block bg-white rounded-card overflow-hidden border border-zinc-200 shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-200"
    >
      <div className="relative aspect-square overflow-hidden bg-zinc-100">
        {firstImage && (
          <Image
            src={firstImage}
            alt={product.name}
            fill
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
            className={cn(
              "object-cover transition-opacity duration-300",
              secondImage ? "group-hover:opacity-0" : "group-hover:scale-105",
            )}
          />
        )}
        {secondImage && (
          <Image
            src={secondImage}
            alt=""
            fill
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
            className="object-cover opacity-0 group-hover:opacity-100 transition-opacity duration-300"
          />
        )}

        <div className="absolute top-2 left-2 flex flex-col gap-1 z-10">
          {product.is_on_sale && product.discount_percent > 0 ? (
            <Badge tone="deal" solid>
              −{product.discount_percent}%
            </Badge>
          ) : isNew ? (
            <Badge tone="success" solid>
              New
            </Badge>
          ) : product.is_featured ? (
            <Badge tone="brand" solid>
              Featured
            </Badge>
          ) : null}
          {lowStock && (
            <Badge tone="warning">Only {product.stock} left</Badge>
          )}
        </div>

        <button
          type="button"
          onClick={handleWishlist}
          aria-label={saved ? "Remove from wishlist" : "Save to wishlist"}
          aria-pressed={saved}
          className="absolute top-2 right-2 z-10 w-8 h-8 rounded-full bg-white/90 backdrop-blur flex items-center justify-center shadow-sm hover:bg-white transition"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            className={cn(saved ? "fill-danger stroke-danger" : "fill-none stroke-zinc-500")}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
        </button>

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
              className="w-9 h-9 rounded-full bg-brand text-brand-fg flex items-center justify-center shadow-md hover:bg-brand-dark transition opacity-0 group-hover:opacity-100 focus:opacity-100"
            >
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="p-3">
        <div className="text-[11px] text-zinc-500 uppercase tracking-wide">
          {product.category.name}
        </div>
        <h3 className="font-medium text-sm mt-0.5 line-clamp-2 min-h-[2.5rem]">{product.name}</h3>

        {(product.rating_count > 0 || hasSold) && (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-zinc-500 whitespace-nowrap overflow-hidden">
            {product.rating_count > 0 && (
              <span className="inline-flex items-center gap-0.5 shrink-0">
                <svg width="12" height="12" viewBox="0 0 20 20" className="fill-amber-400" aria-hidden>
                  <path d="M10 1.5l2.6 5.3 5.9.86-4.25 4.14 1 5.85L10 14.9 4.75 17.65l1-5.85L1.5 7.66l5.9-.86L10 1.5z" />
                </svg>
                <span className="font-medium text-zinc-700">{Number(product.rating_avg).toFixed(1)}</span>
                <span>({product.rating_count})</span>
              </span>
            )}
            {product.rating_count > 0 && hasSold && <span className="text-zinc-300">·</span>}
            {hasSold && <span className="truncate">{formatSold(product.sold_count!)} sold</span>}
          </div>
        )}

        <div className="mt-2">
          <Price price={product.price} compareAt={product.compare_at_price} size="md" showPercent={false} />
        </div>

        {freeShip && (
          <div className="mt-1 text-[11px] font-medium text-success">Free shipping</div>
        )}
      </div>
    </Link>
  );
}
