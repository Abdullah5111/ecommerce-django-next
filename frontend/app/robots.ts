import type { MetadataRoute } from "next";
import { unstable_noStore as noStore } from "next/cache";
import { PRIVATE_PATHS, siteUrl } from "@/lib/sitemap";

export default function robots(): MetadataRoute.Robots {
  // Render per request so SITE_URL is read at runtime; prerendering would
  // bake in the build's value (`export const dynamic` isn't honoured here).
  noStore();
  return {
    rules: { userAgent: "*", allow: "/", disallow: PRIVATE_PATHS },
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
