import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";

const require = createRequire(import.meta.url);
const nextConfig = require("../../next.config.js");

async function headersFor() {
  const rules = await nextConfig.headers();
  const all = rules.find((r: { source: string }) => r.source === "/:path*");
  return Object.fromEntries(
    all.headers.map((h: { key: string; value: string }) => [h.key, h.value])
  ) as Record<string, string>;
}

describe("security headers", () => {
  it("apply to every page", async () => {
    const rules = await nextConfig.headers();
    expect(rules.map((r: { source: string }) => r.source)).toContain("/:path*");
  });

  it("forbid framing the storefront", async () => {
    const h = await headersFor();
    expect(h["X-Frame-Options"]).toBe("DENY");
    expect(h["Content-Security-Policy"]).toBe("frame-ancestors 'none'");
  });

  it("set nosniff and a referrer policy", async () => {
    const h = await headersFor();
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
  });

  it("turn off unused browser features but keep payments for Stripe", async () => {
    const policy = (await headersFor())["Permissions-Policy"];
    for (const feature of ["camera=()", "microphone=()", "geolocation=()"]) {
      expect(policy).toContain(feature);
    }
    expect(policy).toContain('payment=(self "https://js.stripe.com")');
  });
});
