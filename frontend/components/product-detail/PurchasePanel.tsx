"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Product, ProductVariant } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useToast } from "@/lib/useToast";
import { useWishlist } from "@/lib/useWishlist";
import { formatSold } from "@/lib/format";
import { FREE_SHIPPING_THRESHOLD } from "@/lib/constants";
import RatingStars from "@/components/RatingStars";
import Button from "@/components/ui/Button";
import Price from "@/components/ui/Price";
import VariantSelector from "./VariantSelector";

function Trust({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-2 text-sm text-zinc-600">
      <span className="text-zinc-400" aria-hidden>
        {icon}
      </span>
      {children}
    </li>
  );
}

export default function PurchasePanel({ product }: { product: Product }) {
  const [qty, setQty] = useState(1);
  const [deliveryBy, setDeliveryBy] = useState<string | null>(null);
  const [variant, setVariant] = useState<ProductVariant | null>(null);
  const { add } = useCart();
  const { toast } = useToast();
  const { has, toggle } = useWishlist();
  const router = useRouter();

  // Client-only delivery estimate, to avoid an SSR/CSR hydration mismatch at the date boundary.
  useEffect(() => {
    const d = new Date();
    d.setDate(d.getDate() + 4);
    setDeliveryBy(d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }));
  }, []);

  const variants = product.variants ?? [];
  const hasVariants = variants.length > 0;
  // A variant product needs a chosen variant before price/stock are known.
  const needsVariant = hasVariants && !variant;
  const displayPrice = variant ? variant.effective_price : product.price;
  const stock = variant ? variant.stock : hasVariants ? 0 : product.stock;

  const inWishlist = has(product.id);
  const maxQty = Math.max(1, stock);
  const inStock = stock > 0;
  const canAdd = inStock && !needsVariant;
  const freeShip = Number(displayPrice) >= FREE_SHIPPING_THRESHOLD;
  const saved =
    !variant && product.is_on_sale && product.compare_at_price
      ? Number(product.compare_at_price) - Number(product.price)
      : 0;

  // Keep quantity within the selected variant's stock when it changes.
  useEffect(() => {
    setQty((q) => Math.min(Math.max(1, q), Math.max(1, stock)));
  }, [stock]);

  const handleAdd = () => {
    add(product, variant, qty);
    toast("Added to cart", "success");
  };

  const handleBuyNow = () => {
    add(product, variant, qty);
    router.push("/checkout");
  };

  const handleWishlist = () => {
    toggle(product);
    toast(inWishlist ? "Removed from wishlist" : "Saved to wishlist", "success");
  };

  return (
    <div className="md:sticky md:top-4 md:self-start">
      <div className="text-sm text-zinc-500 uppercase tracking-wide">{product.category.name}</div>
      <h1 className="text-2xl md:text-3xl font-bold mt-1">{product.name}</h1>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        {product.rating_count > 0 && (
          <RatingStars value={product.rating_avg} count={product.rating_count} size="md" />
        )}
        {typeof product.sold_count === "number" && product.sold_count > 0 && (
          <span className="text-sm text-zinc-500">{formatSold(product.sold_count)} sold</span>
        )}
      </div>

      <div className="mt-4 rounded-card border border-zinc-200 bg-white shadow-card p-5">
        <Price
          price={displayPrice}
          compareAt={variant ? null : product.compare_at_price}
          size="lg"
        />
        {saved > 0 && (
          <div className="mt-1 text-sm font-medium text-success">You save ${saved.toFixed(2)}</div>
        )}

        {hasVariants && (
          <VariantSelector variants={variants} selected={variant} onSelect={setVariant} />
        )}

        <ul className="mt-4 space-y-2 border-t border-zinc-100 pt-4">
          {deliveryBy && (
            <Trust
              icon={
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 3h15v13H1zM16 8h4l3 3v5h-7V8zM5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z" /></svg>
              }
            >
              Get it by <span className="font-medium text-ink">{deliveryBy}</span>
              {freeShip && <span className="text-success font-medium"> · Free shipping</span>}
            </Trust>
          )}
          {needsVariant ? (
            <li className="text-sm text-zinc-500">Select an option to see availability</li>
          ) : inStock ? (
            stock <= 5 ? (
              <li className="text-sm font-medium text-danger">Only {stock} left — order soon</li>
            ) : stock < 10 ? (
              <li className="text-sm font-medium text-deal-dark">Selling fast — {stock} in stock</li>
            ) : (
              <li className="text-sm text-success">In stock</li>
            )
          ) : (
            <li className="text-sm font-medium text-zinc-500">Currently out of stock</li>
          )}
        </ul>

        {canAdd && (
          <div className="mt-4 flex items-center gap-3">
            <span className="text-sm text-zinc-600">Quantity</span>
            <div className="inline-flex items-center border border-zinc-300 rounded-lg">
              <button
                type="button"
                onClick={() => setQty((q) => Math.max(1, q - 1))}
                disabled={qty <= 1}
                className="px-3 py-2 disabled:text-zinc-300 hover:bg-zinc-50 rounded-l-lg"
                aria-label="Decrease quantity"
              >
                −
              </button>
              <span className="px-4 py-2 min-w-[2.5rem] text-center select-none tabular-nums">{qty}</span>
              <button
                type="button"
                onClick={() => setQty((q) => Math.min(maxQty, q + 1))}
                disabled={qty >= maxQty}
                className="px-3 py-2 disabled:text-zinc-300 hover:bg-zinc-50 rounded-r-lg"
                aria-label="Increase quantity"
              >
                +
              </button>
            </div>
          </div>
        )}

        <div className="mt-5 space-y-2">
          <Button onClick={handleAdd} disabled={!canAdd} fullWidth size="lg">
            {needsVariant ? "Select an option" : inStock ? "Add to cart" : "Out of stock"}
          </Button>
          {canAdd && (
            <Button onClick={handleBuyNow} variant="deal" fullWidth size="lg">
              Buy now
            </Button>
          )}
          <Button onClick={handleWishlist} variant="ghost" fullWidth aria-pressed={inWishlist}>
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              className={inWishlist ? "fill-danger stroke-danger" : "fill-none stroke-current"}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
            {inWishlist ? "Saved" : "Save for later"}
          </Button>
        </div>

        <ul className="mt-5 space-y-2 border-t border-zinc-100 pt-4">
          <Trust icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-9 9zM9 12l2 2 4-4" /></svg>}>
            Free 30-day returns
          </Trust>
          <Trust icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>}>
            Secure checkout
          </Trust>
        </ul>
      </div>
    </div>
  );
}
