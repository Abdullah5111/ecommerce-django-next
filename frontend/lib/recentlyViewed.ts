import type { Product } from "./api";

const KEY = "shop_recent";
const CAP = 12;

export function pushRecent(product: Product): void {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(KEY);
    const list: Product[] = raw ? JSON.parse(raw) : [];
    const deduped = list.filter((p) => p.id !== product.id);
    const next = [product, ...deduped].slice(0, CAP);
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // ignore
  }
}

export function getRecent(excludeId?: number): Product[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const list: Product[] = JSON.parse(raw);
    if (excludeId !== undefined) return list.filter((p) => p.id !== excludeId);
    return list;
  } catch {
    return [];
  }
}
