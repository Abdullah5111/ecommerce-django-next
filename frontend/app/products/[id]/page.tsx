"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type Product } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useToast } from "@/lib/useToast";
import RatingStars from "@/components/RatingStars";

export default function ProductDetail({ params }: { params: { id: string } }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [qty, setQty] = useState(1);
  const { add } = useCart();
  const { toast } = useToast();

  useEffect(() => {
    api.getProduct(params.id).then(setProduct).catch((e) => setError(e.message));
  }, [params.id]);

  const gallery = useMemo(() => {
    if (!product) return [] as { url: string; alt: string }[];
    if (product.images && product.images.length > 0) {
      return [...product.images]
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((img) => ({ url: img.url, alt: img.alt || product.name }));
    }
    if (product.image_url) {
      return [{ url: product.image_url, alt: product.name }];
    }
    return [];
  }, [product]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!product) return <p>Loading…</p>;

  const active = gallery[activeIdx] || gallery[0];
  const maxQty = Math.max(1, product.stock);

  const dec = () => setQty((q) => Math.max(1, q - 1));
  const inc = () => setQty((q) => Math.min(maxQty, q + 1));

  const handleAdd = () => {
    add(product, qty);
    toast("Added to cart", "success");
  };

  return (
    <div className="grid md:grid-cols-2 gap-8">
      <div className="flex gap-3">
        {gallery.length > 1 && (
          <div className="flex flex-col gap-2 w-16 shrink-0">
            {gallery.map((img, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setActiveIdx(i)}
                className={`aspect-square rounded-md overflow-hidden border-2 bg-zinc-100 ${
                  i === activeIdx ? "border-black" : "border-transparent hover:border-zinc-300"
                }`}
                aria-label={`View image ${i + 1}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={img.url} alt={img.alt} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}
        <div className="flex-1 aspect-square bg-zinc-100 rounded-lg overflow-hidden">
          {active && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={active.url} alt={active.alt} className="w-full h-full object-cover" />
          )}
        </div>
      </div>

      <div>
        <div className="text-sm text-zinc-500 uppercase">{product.category.name}</div>
        <h1 className="text-3xl font-bold mt-1">{product.name}</h1>

        {product.rating_count > 0 && (
          <div className="mt-2">
            <RatingStars value={product.rating_avg} count={product.rating_count} size="md" />
          </div>
        )}

        <div className="text-2xl font-semibold mt-4 flex items-baseline gap-3">
          {product.is_on_sale && product.compare_at_price ? (
            <>
              <span className="text-red-600">${product.price}</span>
              <span className="text-base text-zinc-400 line-through font-normal">
                ${product.compare_at_price}
              </span>
              {product.discount_percent > 0 && (
                <span className="text-sm bg-red-600 text-white px-2 py-0.5 rounded font-medium">
                  −{product.discount_percent}%
                </span>
              )}
            </>
          ) : (
            <span>${product.price}</span>
          )}
        </div>

        <p className="text-zinc-700 mt-4 leading-relaxed whitespace-pre-line">{product.description}</p>

        {product.stock < 10 && product.stock > 0 && (
          <div className="text-sm text-amber-700 mt-3">{product.stock} in stock</div>
        )}

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
                –
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
    </div>
  );
}
