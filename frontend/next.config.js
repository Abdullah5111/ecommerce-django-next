// Sent on every page. No full Content-Security-Policy yet: Stripe Elements and
// Google sign-in need a careful allow-list, so only frame-ancestors is set.
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Nobody may frame the storefront (clickjacking). Stripe's own iframes
  // inside our pages are unaffected — this governs who frames *us*.
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  // The store never uses these. `payment` stays allowed for Stripe's iframes
  // (Apple Pay / Google Pay in the Payment Element).
  {
    key: "Permissions-Policy",
    value: 'camera=(), microphone=(), geolocation=(), payment=(self "https://js.stripe.com")',
  },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [{ protocol: "https", hostname: "images.unsplash.com" }],
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

module.exports = nextConfig;
