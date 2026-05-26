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
  listProducts: (q?: string) =>
    request<Paginated<Product>>(`/products/${q ? `?search=${encodeURIComponent(q)}` : ""}`),
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
};
