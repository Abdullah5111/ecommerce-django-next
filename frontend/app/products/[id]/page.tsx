import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { api, type CategoryDetail, type Product, type Review } from "@/lib/api";
import Breadcrumbs from "@/components/Breadcrumbs";
import Gallery from "@/components/product-detail/Gallery";
import PurchasePanel from "@/components/product-detail/PurchasePanel";
import Tabs from "@/components/product-detail/Tabs";
import SpecsTable from "@/components/product-detail/SpecsTable";
import ReviewsSection from "@/components/product-detail/ReviewsSection";
import RelatedRail from "@/components/product-detail/RelatedRail";
import RecentlyViewedRail from "@/components/product-detail/RecentlyViewedRail";
import StickyCta from "@/components/product-detail/StickyCta";

function buildGallery(product: Product): { url: string; alt: string }[] {
  if (product.images && product.images.length > 0) {
    return [...product.images]
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((img) => ({ url: img.url, alt: img.alt || product.name }));
  }
  if (product.image_url) {
    return [{ url: product.image_url, alt: product.name }];
  }
  return [];
}

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  try {
    const product = await api.getProduct(params.id);
    const gallery = buildGallery(product);
    const description = (product.description || "").slice(0, 160);
    return {
      title: `${product.name} — Shop`,
      description,
      openGraph: {
        title: `${product.name} — Shop`,
        description,
        images: gallery.length > 0 ? [{ url: gallery[0].url }] : undefined,
      },
    };
  } catch {
    return { title: "Product — Shop" };
  }
}

export default async function ProductDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const slug = params.id;

  let product: Product;
  try {
    product = await api.getProduct(slug);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("404")) notFound();
    return (
      <div className="text-center py-20">
        <h2 className="text-2xl font-semibold">Backend unreachable</h2>
        <p className="text-zinc-500 mt-2">Start the Django API and refresh.</p>
      </div>
    );
  }

  const [catRes, reviewsRes, relatedRes] = await Promise.allSettled([
    api.getCategoryByPath(product.category.full_slug),
    api.listReviews(slug),
    api.getRelated(slug),
  ]);

  const category: CategoryDetail | null =
    catRes.status === "fulfilled" ? catRes.value : null;
  const reviews: Review[] =
    reviewsRes.status === "fulfilled" ? reviewsRes.value.results : [];
  const reviewCount =
    reviewsRes.status === "fulfilled" ? reviewsRes.value.count : 0;
  const related: Product[] =
    relatedRes.status === "fulfilled" ? relatedRes.value : [];

  const gallery = buildGallery(product);
  const specs = product.specifications || {};
  const ancestors = category?.ancestors ?? [];

  const ratingCount = product.rating_count || 0;
  const ratingAvg = product.rating_avg || "0";

  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    image: gallery.map((g) => g.url),
    description: product.description,
    sku: `PROD-${product.id}`,
    brand: { "@type": "Brand", name: "Shop" },
    offers: {
      "@type": "Offer",
      url: `/products/${product.slug}`,
      priceCurrency: "USD",
      price: product.price,
      availability:
        product.stock > 0
          ? "https://schema.org/InStock"
          : "https://schema.org/OutOfStock",
    },
  };
  if (ratingCount > 0) {
    jsonLd.aggregateRating = {
      "@type": "AggregateRating",
      ratingValue: ratingAvg,
      reviewCount: ratingCount,
    };
  }

  return (
    <div className="pb-24 md:pb-0">
      <Breadcrumbs ancestors={ancestors} current={product.name} />

      <div className="grid md:grid-cols-2 gap-8">
        <Gallery images={gallery} />
        <PurchasePanel product={product} />
      </div>

      <Tabs
        description={
          <p className="text-zinc-700 whitespace-pre-line leading-relaxed">
            {product.description || "No description available."}
          </p>
        }
        specifications={
          Object.keys(specs).length > 0 ? <SpecsTable specs={specs} /> : undefined
        }
        reviews={
          <ReviewsSection
            slug={slug}
            reviews={reviews}
            count={reviewCount}
            ratingAvg={ratingAvg}
            ratingCount={ratingCount}
          />
        }
      />

      <RelatedRail products={related} categoryName={product.category.name} />
      <RecentlyViewedRail product={product} />
      <StickyCta product={product} />

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    </div>
  );
}
