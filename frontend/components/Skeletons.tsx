export function ProductCardSkeleton() {
  return (
    <div className="bg-white rounded-card overflow-hidden border border-zinc-200 shadow-card">
      <div className="skeleton aspect-square" />
      <div className="p-3 space-y-2">
        <div className="skeleton h-2.5 w-16 rounded" />
        <div className="skeleton h-4 w-3/4 rounded" />
        <div className="skeleton h-3 w-24 rounded" />
        <div className="skeleton h-5 w-20 rounded" />
      </div>
    </div>
  );
}

export function ProductGridSkeleton({ count }: { count: number }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  );
}
