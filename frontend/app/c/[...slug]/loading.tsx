import { ProductCardSkeleton } from "@/components/Skeletons";

export default function Loading() {
  return (
    <div>
      <div className="skeleton h-4 w-64 rounded mb-4" />
      <div className="skeleton h-9 w-48 rounded mb-6" />
      <div className="flex flex-col md:flex-row gap-6">
        <div className="md:w-64 shrink-0 space-y-3">
          <div className="skeleton h-40 w-full rounded-card" />
        </div>
        <div className="flex-1 grid grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <ProductCardSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
