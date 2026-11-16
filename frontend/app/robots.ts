import type { MetadataRoute } from "next";
import { PRIVATE_PATHS, siteUrl } from "@/lib/sitemap";

// Read SITE_URL at request time; prerendering would bake in the build's value.
export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: PRIVATE_PATHS },
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
