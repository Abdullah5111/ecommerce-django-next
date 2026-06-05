export function ProductCardSkeleton() {
  return (
    <div className="bg-white rounded-lg overflow-hidden border animate-pulse">
      <div className="aspect-square bg-zinc-200" />
      <div className="p-4 space-y-2">
        <div className="h-3 w-20 bg-zinc-200 rounded" />
        <div className="h-4 w-3/4 bg-zinc-200 rounded" />
        <div className="h-3 w-24 bg-zinc-200 rounded" />
        <div className="h-4 w-16 bg-zinc-200 rounded" />
      </div>
    </div>
  );
}

export function ProductGridSkeleton({ count }: { count: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  );
}
