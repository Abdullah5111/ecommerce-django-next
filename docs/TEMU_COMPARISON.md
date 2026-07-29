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
| Search autocomplete / visual / voice search | ✅ | 🟡 | Debounced typeahead with product suggestions; no visual/voice search |

## Product detail
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Image gallery + lightbox | ✅ | ✅ | |
| Specifications table | ✅ | ✅ | |
| Ratings + reviews | ✅ | ✅ | Histogram + write-review |
| Stock urgency / social proof ("X left") | ✅ | ✅ | "X sold" from order data + stock-urgency hints; no live "X viewing" |
| Variants (size/color/SKU) | ✅ | ✅ | Per-variant stock + optional price override; variant-aware cart, checkout, stock and refunds |
| Product video | ✅ | ❌ | |
| Photo/video reviews | ✅ | 🟡 | Reviewer photos (up to 5, lightbox); no video |
| Verified-purchase badge / helpful votes | ✅ | ✅ | Badge snapshotted from real order data; one helpful vote per user, sortable |
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
| Save for later | ✅ | ✅ | "Save for later" on cart lines ↔ "Move to cart" from a saved section (wishlist-backed) |
| Tax in totals | ✅ | ✅ | Configurable `TAX_RATE` on discounted merchandise; own line, snapshotted on the order, tax-aware refunds |
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
| Social login (Google/Apple/FB) | ✅ | 🟡 | Google sign-in (ID-token verify → JWT, email-linked); Apple/FB not done |
| Notification center | ✅ | ✅ | In-app feed + header bell with unread badge; per-event notifications |

## Engagement, marketplace & platform
| Sub-feature | Temu | Yours | Notes |
|---|---|---|---|
| Transactional emails (verify/reset) | ✅ | ✅ | |
| Order-confirmation / shipping emails | ✅ | ✅ | Emails on every lifecycle event (paid/shipped/delivered/cancelled/refunded) |
| Push notifications | ✅ | ✅ | Web Push (VAPID + service worker); graceful no-op without keys |
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
| ✅ Matched | ~38 | catalog, coupons, cart/wishlist, save-for-later, social proof, lifecycle, returns, accounts, payments, refunds, notifications, order emails, web push, verified-purchase + helpful votes, tax, variants |
| 🟡 Partial | ~7 | google login (no Apple/FB), tracking, wallets, homepage banners, review photos (no video), search autocomplete (no visual/voice) |
| ❌ Not matched | ~16 | multi-vendor, gamification, i18n, BNPL, Q&A |

## Recommended next gaps (impact order)

1. **Q&A** on product detail, and **frequently-bought-together** bundles
2. **New-user / referral discounts**

Recently shipped:
- ~~Search autocomplete~~ — debounced header typeahead (`/products/suggest/`, ≤8 lean matches by name) with thumbnail/price rows, keyboard navigation, and stale-response guarding. Visual/voice search remain out.
- ~~Real payments (Stripe)~~ — PaymentIntent + Elements + webhook, real refunds, keyless mock fallback.
- ~~Order-confirmation / shipping emails~~ — emails on every order lifecycle event.
- ~~Push notifications~~ — in-app notification center + bell, plus Web Push (VAPID), keyless-disabled by default.
- ~~Review enhancements~~ — verified-purchase badge (snapshotted from order data), reviewer photos with a lightbox, and one-per-user helpful votes with most-helpful sorting. Video reviews remain out.
- ~~Tax~~ — configurable `TAX_RATE` applied to discounted merchandise, its own line in the breakdown, snapshotted on the order, with tax-aware refunds. Off by default (0%).
- ~~Product variants~~ — size/color/SKU with per-variant stock and optional price override; option pickers on the PDP, variant-aware cart/checkout/stock/refunds, and SKU/label snapshots on order history. Products without variants are unchanged.

Marketplace-scale items (multi-vendor, gamification, BNPL, i18n) are realistically
out of scope for this portfolio piece.
