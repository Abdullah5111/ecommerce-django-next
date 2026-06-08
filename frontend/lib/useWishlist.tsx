"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Product } from "./api";

type WishlistContextValue = {
  ids: number[];
  items: Product[];
  has: (id: number) => boolean;
  toggle: (product: Product) => void;
  clear: () => void;
};

const WishlistContext = createContext<WishlistContextValue | null>(null);
const KEY = "shop_wishlist";

export function WishlistProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Product[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw) setItems(JSON.parse(raw));
    } catch {
      // ignore parse errors
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(KEY, JSON.stringify(items));
  }, [items, hydrated]);

  const has = useCallback(
    (id: number) => items.some((p) => p.id === id),
    [items]
  );

  const toggle = useCallback((product: Product) => {
    setItems((prev) => {
      const exists = prev.some((p) => p.id === product.id);
      if (exists) return prev.filter((p) => p.id !== product.id);
      return [product, ...prev];
    });
  }, []);

  const clear = useCallback(() => setItems([]), []);

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
