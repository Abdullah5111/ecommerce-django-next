import type { CategoryTreeNode } from "./api";

/** Public origin for absolute URLs in robots.txt / sitemap.xml. Server-only. */
export function siteUrl(): string {
  return (process.env.SITE_URL || "http://localhost:3000").replace(/\/+$/, "");
}

/** Signed-in, transactional or internal pages: nothing for a search engine. */
export const PRIVATE_PATHS = [
  "/account",
  "/cart",
  "/checkout",
  "/orders",
  "/staff",
  "/wishlist",
  "/api",
];

export type SitemapEntry = {
  url: string;
  changeFrequency?: "daily" | "weekly";
  priority?: number;
};

function walk(nodes: CategoryTreeNode[], out: string[]) {
  for (const node of nodes) {
    out.push(node.full_slug);
    walk(node.children, out);
  }
}

/** Home, every category (any depth) and every product, as absolute URLs. */
export function sitemapEntries(
  base: string,
  tree: CategoryTreeNode[],
  productSlugs: string[]
): SitemapEntry[] {
  const categories: string[] = [];
  walk(tree, categories);
  return [
    { url: `${base}/`, changeFrequency: "daily", priority: 1 },
    { url: `${base}/products`, changeFrequency: "daily", priority: 0.8 },
    ...categories.map((slug) => ({
      url: `${base}/c/${slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.7,
    })),
    ...productSlugs.map((slug) => ({
      url: `${base}/products/${encodeURIComponent(slug)}`,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
  ];
}
