"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, type Cart, type Product } from "./api";
import { auth } from "./auth";
import { useAuth } from "./useAuth";

export type CartItem = { product: Product; quantity: number };

type CartContextValue = {
  items: CartItem[];
  add: (product: Product, quantity?: number) => void;
  remove: (productId: number) => void;
  update: (productId: number, quantity: number) => void;
  clear: () => void;
  total: number;
};

const CartContext = createContext<CartContextValue | null>(null);
const KEY = "shop_cart";

function readLocal(): CartItem[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as CartItem[]) : [];
  } catch {
    return [];
  }
}

function fromCart(cart: Cart): CartItem[] {
  return cart.items.map((line) => ({ product: line.product, quantity: line.quantity }));
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [items, setItems] = useState<CartItem[]>([]);
  // Which auth identity the current `items` were loaded for — guards the
  // login-merge from re-running on every auth refresh.
  const syncedFor = useRef<number | "guest" | null>(null);

  // Persist to localStorage only while a guest; logged-in carts live on the server.
  useEffect(() => {
    if (!user) window.localStorage.setItem(KEY, JSON.stringify(items));
  }, [items, user]);

  // Load on mount and whenever auth state changes. On the guest→login transition,
  // merge the local cart into the server (summing quantities) then drop localStorage.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = auth.get();
      if (user && token) {
        if (syncedFor.current === user.id) return;
        const local = readLocal();
        try {
          if (local.length > 0) {
            await api.mergeCart(token, {
              items: local.map((i) => ({ product: i.product.id, quantity: i.quantity })),
            });
            window.localStorage.removeItem(KEY);
          }
          const cart = await api.getCart(token);
          if (!cancelled) {
            setItems(fromCart(cart));
            syncedFor.current = user.id;
          }
        } catch {
          // keep whatever we have on failure
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
      setItems(fromCart(await api.getCart(token)));
    } catch {
      // ignore
    }
  }, []);

  const add = useCallback(
    (product: Product, quantity = 1) => {
      // Optimistic update for snappy UX; server response reconciles (e.g. stock cap).
      setItems((prev) => {
        const existing = prev.find((i) => i.product.id === product.id);
        if (existing) {
          return prev.map((i) =>
            i.product.id === product.id ? { ...i, quantity: i.quantity + quantity } : i,
          );
        }
        return [...prev, { product, quantity }];
      });
      const token = auth.get();
      if (token) {
        api
          .addToCart(token, { product: product.id, quantity })
          .then((cart) => setItems(fromCart(cart)))
          .catch(() => reloadServer());
      }
    },
    [reloadServer],
  );

  const remove = useCallback(
    (productId: number) => {
      setItems((prev) => prev.filter((i) => i.product.id !== productId));
      const token = auth.get();
      if (token) {
        api.removeCartItem(token, productId).then((c) => setItems(fromCart(c))).catch(() => reloadServer());
      }
    },
    [reloadServer],
  );

  const update = useCallback(
    (productId: number, quantity: number) => {
      setItems((prev) =>
        quantity <= 0
          ? prev.filter((i) => i.product.id !== productId)
          : prev.map((i) => (i.product.id === productId ? { ...i, quantity } : i)),
      );
      const token = auth.get();
      if (token) {
        api.updateCartItem(token, productId, quantity).then((c) => setItems(fromCart(c))).catch(() => reloadServer());
      }
    },
    [reloadServer],
  );

  const clear = useCallback(() => {
    setItems([]);
    const token = auth.get();
    if (token) api.clearCart(token).catch(() => {});
  }, []);

  const total = items.reduce((sum, i) => sum + parseFloat(i.product.price) * i.quantity, 0);

  return (
    <CartContext.Provider value={{ items, add, remove, update, clear, total }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside CartProvider");
  return ctx;
}
