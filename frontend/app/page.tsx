import Link from "next/link";
import { api, type Product } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import RailCard from "@/components/RailCard";
import RecommendedRail from "@/components/RecommendedRail";
import SearchBar from "@/components/SearchBar";
import Pagination from "@/components/Pagination";

const PAGE_SIZE = 12;

function buildHomeHref(params: { search?: string }) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  const s = qs.toString();
  return s ? `/?${s}` : "/";
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: { search?: string; category?: string; page?: string };
}) {
  const query = searchParams.search?.trim() || "";
  const category = searchParams.category?.trim() || "";
  const pageNum = Math.max(1, parseInt(searchParams.page || "1", 10) || 1);

  let products: Product[] = [];
  let totalCount = 0;
  let categories: { id: number; name: string; slug: string; full_slug: string; level: number; parent: number | null }[] = [];
  let featured: Product[] = [];
  try {
    const [productsData, categoriesData, featuredResult] = await Promise.all([
      api.listProducts({
        search: query || undefined,
        category: category || undefined,
        page: pageNum,
      }),
      api.listCategories(),
      api.getFeatured().catch(() => [] as Product[]),
    ]);
    products = productsData.results;
    totalCount = productsData.count;
    categories = categoriesData.results;
    featured = featuredResult;
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

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">{heading}</h1>
      <SearchBar />

      <RecommendedRail />

      {featured.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">Featured</h2>
          <div className="flex overflow-x-auto snap-x snap-mandatory gap-4 pb-2 -mx-4 px-4">
            {featured.map((p) => (
              <RailCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-2 mb-6">
        <Link
          href={buildHomeHref({ search: query })}
          className={`px-3 py-1 rounded-full text-sm border ${
            !category ? "bg-black text-white border-black" : "bg-white hover:border-zinc-400"
          }`}
        >
          All
        </Link>
        {categories
          .filter((c) => c.level === 0)
          .map((c) => (
            <Link
              key={c.id}
              href={`/c/${c.full_slug}`}
              className="px-3 py-1 rounded-full text-sm border bg-white hover:border-zinc-400"
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
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {products.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
          <Pagination
            currentPage={pageNum}
            totalPages={totalPages}
            pathname="/"
            searchParams={{
              search: query || undefined,
              category: category || undefined,
            }}
          />
        </>
      )}
    </div>
  );
}
