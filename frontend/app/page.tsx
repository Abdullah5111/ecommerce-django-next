import Link from "next/link";
import { api, type Product } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import RailCard from "@/components/RailCard";
import RecommendedRail from "@/components/RecommendedRail";
import SearchBar from "@/components/SearchBar";
import CategoryFilters from "@/components/CategoryFilters";
import SortDropdown from "@/components/SortDropdown";
import ActiveFilters from "@/components/ActiveFilters";
import Pagination from "@/components/Pagination";
import Hero from "@/components/home/Hero";
import CategoryTiles from "@/components/home/CategoryTiles";
import DealsRail from "@/components/home/DealsRail";
import { PAGE_SIZE } from "@/lib/constants";

function buildHomeHref(params: { search?: string }) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  const s = qs.toString();
  return s ? `/?${s}` : "/";
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: {
    search?: string;
    category?: string;
    page?: string;
    ordering?: string;
    priceMin?: string;
    priceMax?: string;
    inStock?: string;
  };
}) {
  const query = searchParams.search?.trim() || "";
  const category = searchParams.category?.trim() || "";
  const ordering = searchParams.ordering?.trim() || "";
  const priceMin = searchParams.priceMin?.trim() || "";
  const priceMax = searchParams.priceMax?.trim() || "";
  const inStock = searchParams.inStock === "true";
  const pageNum = Math.max(1, parseInt(searchParams.page || "1", 10) || 1);
  // The featured/deals rails only appear on the plain browse view, so skip
  // fetching them entirely when searching, filtering by category, or paginating.
  const browse = !query && !category && pageNum === 1;

  let products: Product[] = [];
  let totalCount = 0;
  let categories: { id: number; name: string; slug: string; full_slug: string; level: number; parent: number | null }[] = [];
  let featured: Product[] = [];
  let deals: Product[] = [];
  try {
    const [productsData, categoriesData, featuredResult, bestsellersResult] = await Promise.all([
      api.listProducts({
        search: query || undefined,
        category: category || undefined,
        ordering: ordering || undefined,
        price_min: priceMin || undefined,
        price_max: priceMax || undefined,
        in_stock: inStock || undefined,
        page: pageNum,
      }),
      api.listCategories(),
      browse ? api.getFeatured().catch(() => [] as Product[]) : Promise.resolve([] as Product[]),
      browse ? api.getBestsellers().catch(() => [] as Product[]) : Promise.resolve([] as Product[]),
    ]);
    products = productsData.results;
    totalCount = productsData.count;
    categories = categoriesData.results;
    featured = featuredResult;
    // Deals = on-sale products, drawn from bestsellers first then featured.
    const seen = new Set<number>();
    deals = [...bestsellersResult, ...featuredResult]
      .filter((p) => p.is_on_sale && !seen.has(p.id) && seen.add(p.id))
      .slice(0, 10);
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
    ? `Results for “${query}” (${totalCount} ${totalCount === 1 ? "result" : "results"})`
    : activeCategory
      ? activeCategory.name
      : "Featured products";

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const topCategories = categories.filter((c) => c.level === 0);

  const paginationParams = {
    search: query || undefined,
    category: category || undefined,
    ordering: ordering || undefined,
    priceMin: priceMin || undefined,
    priceMax: priceMax || undefined,
    inStock: inStock ? "true" : undefined,
  };

  // The filter sidebar narrows the grid on search views, so it drops to 3 cols;
  // the plain browse landing (no sidebar) keeps 4.
  const results =
    products.length === 0 ? (
      <p className="text-zinc-500 py-12 text-center">
        No products found{query ? ` for “${query}”` : ""}
        {activeCategory ? ` in ${activeCategory.name}` : ""}.
      </p>
    ) : (
      <>
        <div className={`grid grid-cols-2 ${browse ? "lg:grid-cols-4" : "lg:grid-cols-3"} gap-4`}>
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
        <Pagination
          currentPage={pageNum}
          totalPages={totalPages}
          pathname="/"
          searchParams={paginationParams}
        />
      </>
    );

  return (
    <div>
      {browse ? (
        <Hero />
      ) : (
        <h1 className="text-3xl font-bold mb-6">{heading}</h1>
      )}
      <SearchBar />

      {browse && <CategoryTiles categories={topCategories} />}

      {browse && <DealsRail products={deals} />}

      {browse && <RecommendedRail />}

      {browse && featured.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">Featured</h2>
          <div className="flex overflow-x-auto snap-x snap-mandatory gap-4 pb-2 -mx-4 px-4">
            {featured.map((p) => (
              <RailCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}

      <div id="catalog" className="flex flex-wrap gap-2 mb-6 scroll-mt-4">
        <Link
          href={buildHomeHref({ search: query })}
          className={`px-3 py-1 rounded-full text-sm border transition-colors ${
            !category
              ? "bg-brand text-brand-fg border-brand"
              : "bg-white border-zinc-300 hover:border-brand hover:text-brand"
          }`}
        >
          All
        </Link>
        {topCategories.map((c) => (
          <Link
            key={c.id}
            href={`/c/${c.full_slug}`}
            className="px-3 py-1 rounded-full text-sm border bg-white border-zinc-300 hover:border-brand hover:text-brand transition-colors"
          >
            {c.name}
          </Link>
        ))}
      </div>

      {browse ? (
        results
      ) : (
        <div className="flex flex-col md:flex-row gap-6">
          <div className="md:w-64 shrink-0 md:sticky md:top-4 md:self-start">
            <CategoryFilters />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <ActiveFilters
                pathname="/"
                search={query || undefined}
                ordering={ordering || undefined}
                priceMin={priceMin || undefined}
                priceMax={priceMax || undefined}
                inStock={inStock ? "true" : undefined}
              />
              <div className="ml-auto">
                <SortDropdown />
              </div>
            </div>
            {results}
          </div>
        </div>
      )}
    </div>
  );
}
