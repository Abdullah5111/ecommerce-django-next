import Link from "next/link";
import { api, type CategoryDetail, type Product } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import SearchBar from "@/components/SearchBar";
import Breadcrumbs from "@/components/Breadcrumbs";
import CategoryFilters from "@/components/CategoryFilters";
import SortDropdown from "@/components/SortDropdown";
import ActiveFilters from "@/components/ActiveFilters";
import Pagination from "@/components/Pagination";

const PAGE_SIZE = 12;

type SearchParams = {
  search?: string;
  ordering?: string;
  priceMin?: string;
  priceMax?: string;
  inStock?: string;
  page?: string;
};

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: { slug: string[] };
  searchParams: SearchParams;
}) {
  const path = (params.slug || []).join("/");
  const pathname = `/c/${path}`;

  const search = searchParams.search?.trim() || "";
  const ordering = searchParams.ordering?.trim() || "";
  const priceMin = searchParams.priceMin?.trim() || "";
  const priceMax = searchParams.priceMax?.trim() || "";
  const inStock = searchParams.inStock === "true";
  const pageNum = Math.max(1, parseInt(searchParams.page || "1", 10) || 1);

  let category: CategoryDetail | null = null;
  let products: Product[] = [];
  let totalCount = 0;
  let backendError = false;
  let notFound = false;

  try {
    const [catRes, prodRes] = await Promise.allSettled([
      api.getCategoryByPath(path),
      api.listProducts({
        category_path: path,
        search: search || undefined,
        ordering: ordering || undefined,
        price_min: priceMin || undefined,
        price_max: priceMax || undefined,
        in_stock: inStock || undefined,
        page: pageNum,
      }),
    ]);

    if (catRes.status === "rejected") {
      const msg = String(catRes.reason?.message || "");
      if (msg.includes("404")) notFound = true;
      else backendError = true;
    } else {
      category = catRes.value;
    }

    if (prodRes.status === "fulfilled") {
      products = prodRes.value.results;
      totalCount = prodRes.value.count;
    } else if (!notFound) {
      backendError = true;
    }
  } catch {
    backendError = true;
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  if (notFound) {
    return (
      <div className="text-center py-20">
        <h2 className="text-2xl font-semibold">Category not found</h2>
        <p className="text-zinc-500 mt-2">
          The category “{path}” doesn’t exist.
        </p>
        <Link
          href="/"
          className="inline-block mt-4 text-sm underline text-zinc-700"
        >
          Back home
        </Link>
      </div>
    );
  }

  if (backendError || !category) {
    return (
      <div className="text-center py-20">
        <h2 className="text-2xl font-semibold">Backend unreachable</h2>
        <p className="text-zinc-500 mt-2">
          Start the Django API and refresh.
        </p>
      </div>
    );
  }

  return (
    <div>
      <Breadcrumbs ancestors={category.ancestors} current={category.name} />

      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
        <h1 className="text-3xl font-bold">{category.name}</h1>
        <span className="text-sm text-zinc-500">
          {totalCount} product{totalCount === 1 ? "" : "s"}
        </span>
      </div>

      <SearchBar />

      {category.children.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {category.children.map((child) => (
            <Link
              key={child.id}
              href={`/c/${child.full_slug}`}
              className="px-3 py-1 rounded-full text-sm border bg-white hover:border-zinc-400"
            >
              {child.name}
            </Link>
          ))}
        </div>
      )}

      <div className="flex flex-col md:flex-row gap-6">
        <div className="md:w-64 shrink-0 md:sticky md:top-4 md:self-start">
          <CategoryFilters />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <ActiveFilters
              pathname={pathname}
              search={search || undefined}
              ordering={ordering || undefined}
              priceMin={priceMin || undefined}
              priceMax={priceMax || undefined}
              inStock={inStock ? "true" : undefined}
            />
            <div className="ml-auto">
              <SortDropdown />
            </div>
          </div>

          {products.length === 0 ? (
            <p className="text-zinc-500 py-12 text-center">
              No products found in {category.name}
              {search ? ` for “${search}”` : ""}.
            </p>
          ) : (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {products.map((p) => (
                  <ProductCard key={p.id} product={p} />
                ))}
              </div>
              <Pagination
                currentPage={pageNum}
                totalPages={totalPages}
                pathname={pathname}
                searchParams={{
                  search: search || undefined,
                  ordering: ordering || undefined,
                  priceMin: priceMin || undefined,
                  priceMax: priceMax || undefined,
                  inStock: inStock ? "true" : undefined,
                }}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
