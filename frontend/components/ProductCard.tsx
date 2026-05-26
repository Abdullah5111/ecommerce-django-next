import Link from "next/link";
import type { Product } from "@/lib/api";

export default function ProductCard({ product }: { product: Product }) {
  return (
    <Link
      href={`/products/${product.slug}`}
      className="group block bg-white rounded-lg overflow-hidden border hover:shadow-md transition"
    >
      <div className="aspect-square overflow-hidden bg-zinc-100">
        {product.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover group-hover:scale-105 transition"
          />
        ) : null}
      </div>
      <div className="p-4">
        <div className="text-xs text-zinc-500 uppercase tracking-wide">{product.category.name}</div>
        <h3 className="font-medium mt-1">{product.name}</h3>
        <div className="mt-2 font-semibold">${product.price}</div>
      </div>
    </Link>
  );
}
