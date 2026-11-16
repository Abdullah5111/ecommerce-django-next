import type { MetadataRoute } from "next";
import { api } from "@/lib/api";
import { siteUrl, sitemapEntries } from "@/lib/sitemap";

// Built per request: prerendering at `next build` would need the API, which
// isn't running in CI or the Docker build. Crawlers fetch it rarely.
export const dynamic = "force-dynamic";

// The product list is paginated (12 a page); stop at a sane ceiling.
const MAX_PAGES = 200;

async function allProductSlugs(): Promise<string[]> {
  const slugs: string[] = [];
  for (let page = 1; page <= MAX_PAGES; page++) {
    const data = await api.listProducts({ page });
    slugs.push(...data.results.map((p) => p.slug));
    if (!data.next) break;
  }
  return slugs;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  try {
    const [tree, slugs] = await Promise.all([api.getCategoryTree(), allProductSlugs()]);
    return sitemapEntries(base, tree, slugs);
  } catch {
    // API down: still serve the static pages rather than an error.
    return sitemapEntries(base, [], []);
  }
}
