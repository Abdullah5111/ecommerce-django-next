import { api } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import SearchBar from "@/components/SearchBar";

export default async function HomePage({
  searchParams,
}: {
  searchParams: { search?: string };
}) {
  const query = searchParams.search?.trim() || "";

  let products = [];
  try {
    const data = await api.listProducts(query || undefined);
    products = data.results;
  } catch (e) {
    return (
      <div className="text-center py-20">
        <h2 className="text-2xl font-semibold">Backend unreachable</h2>
        <p className="text-zinc-500 mt-2">
          Start the Django API and refresh. See README for setup.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">
        {query ? `Results for “${query}”` : "Featured products"}
      </h1>
      <SearchBar />
      {products.length === 0 ? (
        <p className="text-zinc-500 py-12 text-center">
          No products found{query ? ` for “${query}”` : ""}.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
