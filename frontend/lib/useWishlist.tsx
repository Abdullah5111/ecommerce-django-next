"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, type Product } from "./api";
import { auth } from "./auth";
import { useAuth } from "./useAuth";

type WishlistContextValue = {
  ids: number[];
  items: Product[];
  has: (id: number) => boolean;
  toggle: (product: Product) => void;
  clear: () => void;
};

const WishlistContext = createContext<WishlistContextValue | null>(null);
const KEY = "shop_wishlist";

function readLocal(): Product[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Product[]) : [];
  } catch {
    return [];
  }
}

export function WishlistProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [items, setItems] = useState<Product[]>([]);
  const syncedFor = useRef<number | "guest" | null>(null);

  // Persist to localStorage only while a guest.
  useEffect(() => {
    if (!user) window.localStorage.setItem(KEY, JSON.stringify(items));
  }, [items, user]);

  // Merge the guest wishlist into the server (union) on login, then load it.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = auth.get();
      if (user && token) {
        if (syncedFor.current === user.id) return;
        const local = readLocal();
        try {
          if (local.length > 0) {
            await api.mergeWishlist(token, { product_ids: local.map((p) => p.id) });
            window.localStorage.removeItem(KEY);
          }
          const rows = await api.getWishlist(token);
          if (!cancelled) {
            setItems(rows.map((r) => r.product));
            syncedFor.current = user.id;
          }
        } catch {
          // keep current
        }
      } else {
        syncedFor.current = "guest";
        if (!cancelled) setItems(readLocal());
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const reloadServer = useCallback(async () => {
    const token = auth.get();
    if (!token) return;
    try {
      const rows = await api.getWishlist(token);
      setItems(rows.map((r) => r.product));
    } catch {
      // ignore
    }
  }, []);

  const has = useCallback((id: number) => items.some((p) => p.id === id), [items]);

  const toggle = useCallback(
    (product: Product) => {
      const exists = items.some((p) => p.id === product.id);
      setItems((prev) => (exists ? prev.filter((p) => p.id !== product.id) : [product, ...prev]));
      const token = auth.get();
      if (token) {
        const call = exists
          ? api.removeWishlistItem(token, product.id)
          : api.addWishlistItem(token, product.id);
        call.then((rows) => setItems(rows.map((r) => r.product))).catch(() => reloadServer());
      }
    },
    [items, reloadServer],
  );

  const clear = useCallback(() => {
    const token = auth.get();
    const current = items.map((p) => p.id);
    setItems([]);
    if (token) {
      current.forEach((id) => api.removeWishlistItem(token, id).catch(() => {}));
    }
  }, [items]);

  const ids = items.map((p) => p.id);

  return (
    <WishlistContext.Provider value={{ ids, items, has, toggle, clear }}>
      {children}
    </WishlistContext.Provider>
  );
}

export function useWishlist() {
  const ctx = useContext(WishlistContext);
  if (!ctx) throw new Error("useWishlist must be used inside WishlistProvider");
  return ctx;
}
