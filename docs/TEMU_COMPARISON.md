# Feature Comparison: This Store vs. Temu

A feature-by-feature comparison of this project against **Temu** (a large multi-vendor
marketplace). Legend: ✅ matched · 🟡 partial / stub · ❌ not present.

> **Framing:** Temu is a multi-vendor marketplace at massive scale. Many of its
> features (multi-seller, gamification, BNPL, logistics integrations) are
> intentionally out of scope for a single-store portfolio app — their absence is
> a scope decision, not a defect.

## Catalog & discovery
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Categories (hierarchical) | ✅ | ✅ | Multi-level, landing pages, mega-menu, breadcrumbs |
| Search | ✅ | ✅ | Postgres full-text |
| Filters (price, stock, category) | ✅ | ✅ | Faceted |
| Sort (price, newest, featured) | ✅ | ✅ | |
| Featured / bestsellers / related | ✅ | ✅ | Cached endpoints |
| Recently viewed | ✅ | ✅ | |
| Personalized feed / recommendations | ✅ | ✅ | "Recommended for you" rail from purchase/wishlist/cart affinity, featured fallback |
| Flash / lightning deals + countdowns | ✅ | ❌ | |
| Homepage banners / carousels | ✅ | 🟡 | Featured grid only |
| Search autocomplete / visual / voice search | ✅ | ❌ | |

## Product detail
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Image gallery + lightbox | ✅ | ✅ | |
| Specifications table | ✅ | ✅ | |
| Ratings + reviews | ✅ | ✅ | Histogram + write-review |
| Stock urgency / social proof ("X left") | ✅ | 🟡 | Stock-urgency hints; no "X sold / X viewing" |
| Variants (size/color/SKU) | ✅ | ❌ | Single price/stock per product |
| Product video | ✅ | ❌ | |
| Photo/video reviews | ✅ | ❌ | Text reviews only |
| Verified-purchase badge / helpful votes | ✅ | ❌ | |
| Q&A | ✅ | ❌ | |
| Frequently-bought-together / bundles | ✅ | ❌ | |

## Pricing & promotions
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Coupons (%, fixed, free-ship, BOGO) | ✅ | ✅ | Full system w/ constraints + scoping |
| Free-shipping threshold | ✅ | ✅ | Flat fee, free over $50 |
| Sale / compare-at price | ✅ | ✅ | |
| New-user / referral discounts | ✅ | ❌ | |
| Gamification (spin wheel, daily check-in) | ✅ | ❌ | |

## Cart & checkout
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Persistent cart (cross-device) | ✅ | ✅ | Server-backed + guest merge on login |
| Address book | ✅ | ✅ | |
| Order summary (subtotal/discount/shipping/total) | ✅ | ✅ | |
| Guest cart | ✅ | ✅ | localStorage, merges on login |
| Save for later | ✅ | 🟡 | Wishlist covers part of this |
| Tax in totals | ✅ | ❌ | Explicitly deferred |
| Express / one-click checkout | ✅ | ❌ | |

## Payments
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Card payments | ✅ | ✅ | Stripe (test mode) — PaymentIntent + Elements + webhook; mock fallback without keys |
| PayPal / wallets (Apple/Google Pay) | ✅ | 🟡 | Stripe `automatic_payment_methods` surfaces wallets where eligible |
| BNPL (Klarna/Afterpay) | ✅ | ❌ | |
| Store credit / wallet | ✅ | ❌ | |

## Orders, fulfillment & returns
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Order lifecycle (pay→ship→deliver) | ✅ | ✅ | With audit timeline |
| Tracking number | ✅ | 🟡 | Stored/shown; no carrier-API live tracking |
| Cancellation | ✅ | ✅ | Restock + coupon release |
| Returns / RMA (line-item) | ✅ | ✅ | Request→approve→receive→refund |
| Refunds | ✅ | ✅ | Real Stripe refunds on cancel/return when keys set; mock otherwise |
| Order history | ✅ | ✅ | |
| Delivery guarantee credits | ✅ | ❌ | |

## Accounts
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Register / login | ✅ | ✅ | JWT, by username or email |
| Email verification | ✅ | ✅ | |
| Password reset | ✅ | ✅ | |
| Profile + avatar | ✅ | ✅ | |
| Phone verification | ✅ | ✅ | OTP flow |
| Wishlist / favorites | ✅ | ✅ | Server-backed |
| Social login (Google/Apple/FB) | ✅ | ❌ | |
| Notification center | ✅ | 🟡 | Preferences page is a stub |

## Engagement, marketplace & platform
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Transactional emails (verify/reset) | ✅ | ✅ | |
| Order-confirmation / shipping emails | ✅ | ❌ | |
| Push notifications | ✅ | ❌ | |
| Referral / affiliate program | ✅ | ❌ | |
| Multi-vendor marketplace + seller storefronts | ✅ | ❌ | Single-store |
| Group buying / social feed | ✅ | ❌ | |
| Multi-currency / multi-language | ✅ | ❌ | Single currency, English |
| Buyer protection / dispute resolution | ✅ | ❌ | |
| Admin / ops tooling | ✅ | ✅ | Django admin (products, orders, coupons, returns, etc.) |
| Performance (indexes, caching, image opt) | ✅ | ✅ | DB indexes, cached endpoints, `next/image` |

## Summary

| Status | Count (approx) | Examples |
|---|---|---|
| ✅ Matched | ~30 | catalog, coupons, persistent cart/wishlist, lifecycle, returns, accounts, card payments, refunds |
| 🟡 Partial | ~7 | tracking, wallets, social proof, notifications, save-for-later |
| ❌ Not matched | ~23 | tax, variants, multi-vendor, gamification, social login, i18n, push/emails, BNPL |

## Recommended next gaps (impact order)

1. **Tax** in the totals breakdown (structure already supports it)
2. **Product variants** (size/color/SKU)
3. **Order-confirmation / shipping emails**
4. **Review enhancements** (photos, verified-purchase badge, helpful votes)

~~Real payments (Stripe)~~ — done: PaymentIntent + Elements + webhook, real refunds, with a
keyless mock fallback for demos.

Marketplace-scale items (multi-vendor, gamification, BNPL, i18n) are realistically
out of scope for this portfolio piece.
