import Image from "next/image";
import Link from "next/link";
import type { Product } from "@/lib/api";
import Price from "@/components/ui/Price";

export default function RailCard({ product }: { product: Product }) {
  const image = product.images?.[0]?.url || product.image_url;

  return (
    <Link
      href={`/products/${product.slug}`}
      className="group snap-start shrink-0 w-56 sm:w-64 bg-white rounded-card overflow-hidden border border-zinc-200 shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all"
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
        <div className="mt-1">
          <Price price={product.price} compareAt={product.compare_at_price} size="md" showPercent={false} />
        </div>
      </div>
    </Link>
  );
}
