import { afterEach, describe, expect, it, vi } from "vitest";

import type { CategoryTreeNode } from "../api";
import { PRIVATE_PATHS, siteUrl, sitemapEntries } from "../sitemap";
import robots from "../../app/robots";

function node(full_slug: string, children: CategoryTreeNode[] = []): CategoryTreeNode {
  return { id: 0, name: full_slug, slug: full_slug, full_slug, level: 0, children };
}

afterEach(() => vi.unstubAllEnvs());

describe("sitemap entries", () => {
  it("lists home, nested categories and products as absolute URLs", () => {
    const tree = [node("audio", [node("audio/headphones")]), node("gear")];
    const urls = sitemapEntries("https://shop.example.com", tree, ["noise-cancel-x", "a b"]).map(
      (e) => e.url
    );
    expect(urls).toEqual([
      "https://shop.example.com/",
      "https://shop.example.com/products",
      "https://shop.example.com/c/audio",
      "https://shop.example.com/c/audio/headphones",
      "https://shop.example.com/c/gear",
      "https://shop.example.com/products/noise-cancel-x",
      "https://shop.example.com/products/a%20b",
    ]);
  });
});

describe("site URL", () => {
  it("comes from SITE_URL without a trailing slash", () => {
    vi.stubEnv("SITE_URL", "https://shop.example.com/");
    expect(siteUrl()).toBe("https://shop.example.com");
  });
});

describe("robots.txt", () => {
  it("keeps crawlers out of private pages and points at the sitemap", () => {
    vi.stubEnv("SITE_URL", "https://shop.example.com");
    const r = robots();
    expect(r.rules).toEqual({ userAgent: "*", allow: "/", disallow: PRIVATE_PATHS });
    expect(PRIVATE_PATHS).toEqual(expect.arrayContaining(["/account", "/checkout", "/staff"]));
    expect(r.sitemap).toBe("https://shop.example.com/sitemap.xml");
  });
});
