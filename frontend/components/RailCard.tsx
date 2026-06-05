import Image from "next/image";
import Link from "next/link";
import type { Product } from "@/lib/api";

export default function RailCard({ product }: { product: Product }) {
  const image = product.images?.[0]?.url || product.image_url;

  return (
    <Link
      href={`/products/${product.slug}`}
      className="group snap-start shrink-0 w-64 bg-white rounded-lg overflow-hidden border hover:shadow-md transition"
    >
      <div className="relative aspect-square bg-zinc-100 overflow-hidden">
        {image ? (
          <Image
            src={image}
            alt={product.name}
            fill
            sizes="256px"
            className="object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : null}
      </div>
      <div className="p-3">
        <div className="text-xs text-zinc-500 uppercase tracking-wide truncate">
          {product.category?.name}
        </div>
        <h3 className="font-medium mt-1 line-clamp-1">{product.name}</h3>
        <div className="mt-1 font-semibold flex items-baseline gap-2">
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
