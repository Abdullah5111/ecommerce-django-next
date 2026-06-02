import Link from "next/link";
import { api } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import SearchBar from "@/components/SearchBar";

function buildHref(params: { search?: string; category?: string }) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.category) qs.set("category", params.category);
  const s = qs.toString();
  return s ? `/?${s}` : "/";
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: { search?: string; category?: string };
}) {
  const query = searchParams.search?.trim() || "";
  const category = searchParams.category?.trim() || "";

  let products = [];
  let categories: { id: number; name: string; slug: string }[] = [];
  try {
    const [productsData, categoriesData] = await Promise.all([
      api.listProducts({ search: query || undefined, category: category || undefined }),
      api.listCategories(),
    ]);
    products = productsData.results;
    categories = categoriesData.results;
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

  const activeCategory = categories.find((c) => c.slug === category);
  const heading = query
    ? `Results for “${query}”`
    : activeCategory
      ? activeCategory.name
      : "Featured products";

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">{heading}</h1>
      <SearchBar />

      <div className="flex flex-wrap gap-2 mb-6">
        <Link
          href={buildHref({ search: query })}
          className={`px-3 py-1 rounded-full text-sm border ${
            !category ? "bg-black text-white border-black" : "bg-white hover:border-zinc-400"
          }`}
        >
          All
        </Link>
        {categories.map((c) => (
          <Link
            key={c.id}
            href={buildHref({ search: query, category: c.slug })}
            className={`px-3 py-1 rounded-full text-sm border ${
              category === c.slug
                ? "bg-black text-white border-black"
                : "bg-white hover:border-zinc-400"
            }`}
          >
            {c.name}
          </Link>
        ))}
      </div>

      {products.length === 0 ? (
        <p className="text-zinc-500 py-12 text-center">
          No products found{query ? ` for “${query}”` : ""}
          {activeCategory ? ` in ${activeCategory.name}` : ""}.
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
