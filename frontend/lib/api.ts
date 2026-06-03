const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export type Category = { id: number; name: string; slug: string };

export type Product = {
  id: number;
  name: string;
  slug: string;
  description: string;
  price: string;
  stock: number;
  image_url: string;
  category: Category;
};

export type OrderItem = {
  id: number;
  product: number;
  product_name: string;
  quantity: number;
  unit_price: string;
  subtotal: string;
};

export type Order = {
  id: number;
  status: "pending" | "paid" | "shipped" | "delivered" | "cancelled";
  shipping_address: string;
  total: string;
  items: OrderItem[];
  created_at: string;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  listProducts: (opts: { search?: string; category?: string } = {}) => {
    const qs = new URLSearchParams();
    if (opts.search) qs.set("search", opts.search);
    if (opts.category) qs.set("category__slug", opts.category);
    const suffix = qs.toString();
    return request<Paginated<Product>>(`/products/${suffix ? `?${suffix}` : ""}`);
  },
  getProduct: (slug: string) => request<Product>(`/products/${slug}/`),
  listCategories: () => request<Paginated<Category>>(`/categories/`),
  login: (username: string, password: string) =>
    request<{ access: string; refresh: string }>(`/auth/token/`, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  register: (data: { username: string; email: string; password: string }) =>
    request<unknown>(`/auth/register/`, { method: "POST", body: JSON.stringify(data) }),
  createOrder: (token: string, payload: {
    shipping_address: string;
    items: { product: number; quantity: number }[];
  }) =>
    request<{ id: number; total: string }>(`/orders/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
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
  me: (token: string) =>
    request<{
      id: number;
      username: string;
      email: string;
      first_name: string;
      last_name: string;
    }>(`/auth/me/`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  logout: (refresh: string) =>
    request<unknown>(`/auth/logout/`, {
      method: "POST",
      body: JSON.stringify({ refresh }),
    }),
};
