"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Product } from "@/lib/api";
import { useCart } from "@/lib/cart";

export default function ProductDetail({ params }: { params: { id: string } }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { add } = useCart();
  const router = useRouter();

  useEffect(() => {
    api.getProduct(params.id).then(setProduct).catch((e) => setError(e.message));
  }, [params.id]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!product) return <p>Loading…</p>;

  return (
    <div className="grid md:grid-cols-2 gap-8">
      <div className="aspect-square bg-zinc-100 rounded-lg overflow-hidden">
        {product.image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
        )}
      </div>
      <div>
        <div className="text-sm text-zinc-500 uppercase">{product.category.name}</div>
        <h1 className="text-3xl font-bold mt-1">{product.name}</h1>
        <div className="text-2xl font-semibold mt-4">${product.price}</div>
        <p className="text-zinc-700 mt-4 leading-relaxed">{product.description}</p>
        <div className="text-sm text-zinc-500 mt-2">{product.stock} in stock</div>
        <button
          onClick={() => {
            add(product);
            router.push("/cart");
          }}
          className="mt-6 bg-black text-white px-6 py-3 rounded font-medium hover:bg-zinc-800"
          disabled={product.stock === 0}
        >
          {product.stock > 0 ? "Add to cart" : "Out of stock"}
        </button>
      </div>
    </div>
  );
}
