import { ProductGridSkeleton } from "@/components/Skeletons";

export default function Loading() {
  return (
    <div>
      <div className="skeleton h-9 w-56 rounded mb-6" />
      <div className="skeleton h-11 w-full max-w-xl rounded mb-6" />
      <ProductGridSkeleton count={8} />
    </div>
  );
}
