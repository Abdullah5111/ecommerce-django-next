import { auth } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export type Category = {
  id: number;
  name: string;
  slug: string;
  full_slug: string;
  level: number;
  parent: number | null;
};

export type CategoryTreeNode = {
  id: number;
  name: string;
  slug: string;
  full_slug: string;
  level: number;
  children: CategoryTreeNode[];
};

export type CategoryRef = {
  id: number;
  name: string;
  slug: string;
  full_slug: string;
};

export type CategoryDetail = {
  id: number;
  name: string;
  slug: string;
  full_slug: string;
  level: number;
  ancestors: CategoryRef[];
  children: CategoryRef[];
};

export type ProductImage = {
  id: number;
  url: string;
  alt: string;
  sort_order: number;
};

export type Product = {
  id: number;
  name: string;
  slug: string;
  description: string;
  price: string;
  stock: number;
  image_url: string;
  category: Category;
  compare_at_price: string | null;
  rating_avg: string;
  rating_count: number;
  images: ProductImage[];
  is_on_sale: boolean;
  discount_percent: number;
  is_featured: boolean;
  created_at?: string;
  specifications?: Record<string, string>;
};

export type Review = {
  id: number;
  rating: number;
  title: string;
  body: string;
  author_name: string;
  created_at: string;
};

export type OrderItem = {
  id: number;
  product: number;
  product_name: string;
  quantity: number;
  unit_price: string;
  subtotal: string;
};

export type OrderEvent = {
  id: number;
  message: string;
  to_status: string;
  actor_name: string | null;
  created_at: string;
};

export type ReturnReason =
  | "defective" | "wrong_item" | "not_as_described" | "no_longer_needed" | "other";

export type ReturnLine = {
  id: number;
  order_item: number;
  product_name: string;
  quantity: number;
  reason: ReturnReason;
  note: string;
};

export type ReturnRequest = {
  id: number;
  order: number;
  status: "requested" | "approved" | "received" | "refunded" | "rejected";
  refund_amount: string;
  staff_note: string;
  created_at: string;
  decided_at: string | null;
  received_at: string | null;
  refunded_at: string | null;
  lines: ReturnLine[];
};

export type CartLine = { id: number; product: Product; quantity: number };

export type Cart = { id: number; items: CartLine[]; total: string };

export type WishlistEntry = { id: number; product: Product; created_at: string };

export type Order = {
  id: number;
  status: "pending" | "paid" | "shipped" | "delivered" | "cancelled" | "partially_refunded" | "refunded";
  shipping_address: string;
  ship_recipient: string;
  ship_phone: string;
  ship_line1: string;
  ship_line2: string;
  ship_city: string;
  ship_state: string;
  ship_postal_code: string;
  ship_country: string;
  total: string;
  subtotal: string;
  discount_total: string;
  shipping_total: string;
  coupon_code: string;
  items: OrderItem[];
  created_at: string;
  paid_at: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  cancelled_at: string | null;
  tracking_number: string;
  tracking_carrier: string;
  refunded_total: string;
  events: OrderEvent[];
};

export type QuoteResult = {
  subtotal: string;
  discount_total: string;
  shipping_total: string;
  grand_total: string;
  coupon_code: string | null;
  coupon_error: string | null;
};

export type PaymentIntentResult = {
  client_secret: string;
  publishable_key: string;
  mock: boolean;
};

export type Address = {
  id: number;
  label: string;
  recipient: string;
  phone: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  is_default_shipping: boolean;
  is_default_billing: boolean;
  created_at: string;
  updated_at: string;
};

export type AddressInput = {
  label: string;
  recipient: string;
  phone: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  is_default_shipping?: boolean;
  is_default_billing?: boolean;
};

export type Gender = "" | "female" | "male" | "nonbinary" | "prefer_not_to_say";

export type Me = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  address: string;
  phone: string;
  email_verified: boolean;
  phone_verified: boolean;
  avatar: string | null;
  display_name: string;
  bio: string;
  date_of_birth: string | null;
  gender: Gender;
};

export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function request<T>(path: string, init: RequestInit = {}, _retry = false): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    cache: "no-store",
  });

  if (res.status === 401 && !_retry && typeof window !== "undefined") {
    const refreshToken = auth.getRefresh();
    const originalError = new Error(`API 401: ${await res.clone().text()}`);

    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${API_URL}/auth/token/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
          cache: "no-store",
        });
        if (refreshRes.ok) {
          const data = (await refreshRes.json()) as { access: string; refresh?: string };
          auth.set(data.access, data.refresh);

          // Swap Authorization header on retry if the original call had one
          const originalHeaders = (init.headers || {}) as Record<string, string>;
          const hadAuth = Object.keys(originalHeaders).some(
            (k) => k.toLowerCase() === "authorization"
          );
          let retryInit = init;
          if (hadAuth) {
            const newHeaders: Record<string, string> = {};
            for (const [k, v] of Object.entries(originalHeaders)) {
              if (k.toLowerCase() !== "authorization") newHeaders[k] = v;
            }
            newHeaders["Authorization"] = `Bearer ${data.access}`;
            retryInit = { ...init, headers: newHeaders };
          }
          return request<T>(path, retryInit, true);
        }
      } catch {
        // fall through to clear + redirect
      }
    }

    auth.clear();
    window.location.href =
      "/login?next=" + encodeURIComponent(window.location.pathname + window.location.search);
    throw originalError;
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  listProducts: (
    opts: {
      search?: string;
      category?: string;
      category_path?: string;
      price_min?: string | number;
      price_max?: string | number;
      in_stock?: boolean;
      ordering?: string;
      page?: number;
    } = {}
  ) => {
    const qs = new URLSearchParams();
    if (opts.search) qs.set("search", opts.search);
    if (opts.category) qs.set("category__slug", opts.category);
    if (opts.category_path) qs.set("category_path", opts.category_path);
    if (opts.price_min !== undefined && opts.price_min !== "")
      qs.set("price__gte", String(opts.price_min));
    if (opts.price_max !== undefined && opts.price_max !== "")
      qs.set("price__lte", String(opts.price_max));
    if (opts.in_stock) qs.set("in_stock", "true");
    if (opts.ordering) qs.set("ordering", opts.ordering);
    if (opts.page && opts.page > 1) qs.set("page", String(opts.page));
    const suffix = qs.toString();
    return request<Paginated<Product>>(`/products/${suffix ? `?${suffix}` : ""}`);
  },
  getProduct: (slug: string) => request<Product>(`/products/${slug}/`),
  listReviews: (slug: string, page?: number) => {
    const qs = page && page > 1 ? `?page=${page}` : "";
    return request<Paginated<Review>>(`/products/${slug}/reviews/${qs}`);
  },
  postReview: (
    token: string,
    slug: string,
    payload: { rating: number; title?: string; body?: string }
  ) =>
    request<Review>(`/products/${slug}/reviews/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  getRelated: (slug: string) => request<Product[]>(`/products/${slug}/related/`),
  getFeatured: () => request<Product[]>(`/products/featured/`),
  getBestsellers: () => request<Product[]>(`/products/bestsellers/`),
  getRecommended: (token?: string) =>
    request<Product[]>(
      `/products/recommended/`,
      token ? { headers: { Authorization: `Bearer ${token}` } } : {},
    ),
  listCategories: () => request<Paginated<Category>>(`/categories/`),
  getCategoryTree: () => request<CategoryTreeNode[]>(`/categories/tree/`),
  getCategoryByPath: (path: string) =>
    request<CategoryDetail>(`/categories/by-path/?path=${encodeURIComponent(path)}`),
  login: (username: string, password: string) =>
    request<{ access: string; refresh: string }>(`/auth/token/`, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  register: (data: { username: string; email: string; password: string }) =>
    request<unknown>(`/auth/register/`, { method: "POST", body: JSON.stringify(data) }),
  createOrder: (
    token: string,
    payload:
      | {
          shipping_address_id: number;
          items: { product: number; quantity: number }[];
          coupon_code?: string;
        }
      | {
          shipping_address: string;
          items: { product: number; quantity: number }[];
          coupon_code?: string;
        }
  ) =>
    request<{ id: number; total: string }>(`/orders/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  quoteOrder: (
    token: string,
    payload: { code?: string; items: { product: number; quantity: number }[] }
  ) =>
    request<QuoteResult>(`/coupons/quote/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  listAddresses: (token: string) =>
    request<Paginated<Address>>(`/auth/addresses/`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((p) => p.results),
  createAddress: (token: string, payload: AddressInput) =>
    request<Address>(`/auth/addresses/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  getAddress: (token: string, id: number) =>
    request<Address>(`/auth/addresses/${id}/`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  updateAddress: (token: string, id: number, payload: AddressInput) =>
    request<Address>(`/auth/addresses/${id}/`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  deleteAddress: (token: string, id: number) =>
    request<void>(`/auth/addresses/${id}/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }),
  setDefaultAddress: (token: string, id: number) =>
    request<Address>(`/auth/addresses/${id}/set-default/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
  createPaymentIntent: (token: string, orderId: number) =>
    request<PaymentIntentResult>(`/orders/${orderId}/create-payment-intent/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
  payOrder: (token: string, orderId: number) =>
    request<unknown>(`/orders/${orderId}/pay/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
  listOrders: (token: string) =>
    request<Paginated<Order>>(`/orders/`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  getOrder: (token: string, id: number) =>
    request<Order>(`/orders/${id}/`, { headers: { Authorization: `Bearer ${token}` } }),
  cancelOrder: (token: string, id: number) =>
    request<Order>(`/orders/${id}/cancel/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
  listReturns: (token: string) =>
    request<Paginated<ReturnRequest>>(`/returns/`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  createReturn: (
    token: string,
    payload: { order: number; lines: { order_item: number; quantity: number; reason: ReturnReason; note?: string }[] }
  ) =>
    request<ReturnRequest>(`/returns/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  getCart: (token: string) =>
    request<Cart>(`/cart/`, { headers: { Authorization: `Bearer ${token}` } }),
  addToCart: (token: string, payload: { product: number; quantity: number }) =>
    request<Cart>(`/cart/items/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  updateCartItem: (token: string, productId: number, quantity: number) =>
    request<Cart>(`/cart/items/${productId}/`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ quantity }),
    }),
  removeCartItem: (token: string, productId: number) =>
    request<Cart>(`/cart/items/${productId}/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }),
  clearCart: (token: string) =>
    request<Cart>(`/cart/`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }),
  mergeCart: (token: string, payload: { items: { product: number; quantity: number }[] }) =>
    request<Cart>(`/cart/merge/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  getWishlist: (token: string) =>
    request<WishlistEntry[]>(`/wishlist/`, { headers: { Authorization: `Bearer ${token}` } }),
  addWishlistItem: (token: string, productId: number) =>
    request<WishlistEntry[]>(`/wishlist/items/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ product: productId }),
    }),
  removeWishlistItem: (token: string, productId: number) =>
    request<WishlistEntry[]>(`/wishlist/items/${productId}/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }),
  mergeWishlist: (token: string, payload: { product_ids: number[] }) =>
    request<WishlistEntry[]>(`/wishlist/merge/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  me: (token: string) =>
    request<Me>(`/auth/me/`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  updateMe: (
    token: string,
    payload: {
      first_name?: string;
      last_name?: string;
      address?: string;
      display_name?: string;
      bio?: string;
      date_of_birth?: string | null;
      gender?: Gender;
    }
  ) =>
    request<Me>(`/auth/me/`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  uploadAvatar: async (token: string, file: File): Promise<Me> => {
    const fd = new FormData();
    fd.append("avatar", file);
    // Multipart: let the browser set Content-Type (with boundary), so this
    // bypasses the JSON `request` helper.
    const res = await fetch(`${API_URL}/auth/me/avatar/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return (await res.json()) as Me;
  },
  deleteAvatar: (token: string) =>
    request<void>(`/auth/me/avatar/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }),
  sendPhoneCode: (token: string, phone: string) =>
    request<{ detail: string }>(`/auth/phone/send-code/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ phone }),
    }),
  verifyPhone: (token: string, code: string) =>
    request<Me>(`/auth/phone/verify/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ code }),
    }),
  logout: (refresh: string) =>
    request<unknown>(`/auth/logout/`, {
      method: "POST",
      body: JSON.stringify({ refresh }),
    }),
  forgotPassword: (email: string) =>
    request<{ detail: string }>(`/auth/forgot-password/`, {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (uid: string, token: string, new_password: string) =>
    request<{ detail: string }>(`/auth/reset-password/`, {
      method: "POST",
      body: JSON.stringify({ uid, token, new_password }),
    }),
  verifyEmail: (uid: string, token: string) =>
    request<{ detail: string }>(`/auth/verify-email/`, {
      method: "POST",
      body: JSON.stringify({ uid, token }),
    }),
};
