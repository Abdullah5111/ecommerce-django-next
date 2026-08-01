"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, type Cart, type Product, type ProductVariant } from "./api";
import { auth } from "./auth";
import { useAuth } from "./useAuth";

export type CartItem = {
  product: Product;
  variant: ProductVariant | null;
  quantity: number;
};

type CartContextValue = {
  items: CartItem[];
  add: (product: Product, variant?: ProductVariant | null, quantity?: number) => void;
  remove: (productId: number, variantId?: number | null) => void;
  update: (productId: number, variantId: number | null, quantity: number) => void;
  clear: () => void;
  total: number;
};

const CartContext = createContext<CartContextValue | null>(null);
const KEY = "shop_cart";

// A cart line is keyed by product *and* variant, so one product under two variants is two lines.
function lineKey(productId: number, variantId: number | null | undefined): string {
  return `${productId}:${variantId ?? ""}`;
}

function unitPrice(item: CartItem): number {
  return parseFloat(item.variant ? item.variant.effective_price : item.product.price);
}

function readLocal(): CartItem[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as CartItem[]) : [];
  } catch {
    return [];
  }
}

function fromCart(cart: Cart): CartItem[] {
  return cart.items.map((line) => ({
    product: line.product,
    variant: line.variant,
    quantity: line.quantity,
  }));
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [items, setItems] = useState<CartItem[]>([]);
  // Auth identity the current `items` were loaded for; guards the login-merge from re-running.
  const syncedFor = useRef<number | "guest" | null>(null);

  // Persist to localStorage only while a guest; logged-in carts live on the server.
  useEffect(() => {
    if (!user) window.localStorage.setItem(KEY, JSON.stringify(items));
  }, [items, user]);

  // Load on auth change; on the guest→login transition, merge the local cart into the
  // server (summing quantities) then drop localStorage.
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
              items: local.map((i) => ({
                product: i.product.id,
                variant: i.variant?.id ?? null,
                quantity: i.quantity,
              })),
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
    (product: Product, variant: ProductVariant | null = null, quantity = 1) => {
      const key = lineKey(product.id, variant?.id ?? null);
      // Optimistic update for snappy UX; server response reconciles (e.g. stock cap).
      setItems((prev) => {
        const existing = prev.find(
          (i) => lineKey(i.product.id, i.variant?.id ?? null) === key,
        );
        if (existing) {
          return prev.map((i) =>
            lineKey(i.product.id, i.variant?.id ?? null) === key
              ? { ...i, quantity: i.quantity + quantity }
              : i,
          );
        }
        return [...prev, { product, variant, quantity }];
      });
      const token = auth.get();
      if (token) {
        api
          .addToCart(token, { product: product.id, variant: variant?.id ?? null, quantity })
          .then((cart) => setItems(fromCart(cart)))
          .catch(() => reloadServer());
      }
    },
    [reloadServer],
  );

  const remove = useCallback(
    (productId: number, variantId: number | null = null) => {
      const key = lineKey(productId, variantId);
      setItems((prev) =>
        prev.filter((i) => lineKey(i.product.id, i.variant?.id ?? null) !== key),
      );
      const token = auth.get();
      if (token) {
        api
          .removeCartItem(token, productId, variantId)
          .then((c) => setItems(fromCart(c)))
          .catch(() => reloadServer());
      }
    },
    [reloadServer],
  );

  const update = useCallback(
    (productId: number, variantId: number | null, quantity: number) => {
      const key = lineKey(productId, variantId);
      setItems((prev) =>
        quantity <= 0
          ? prev.filter((i) => lineKey(i.product.id, i.variant?.id ?? null) !== key)
          : prev.map((i) =>
              lineKey(i.product.id, i.variant?.id ?? null) === key
                ? { ...i, quantity }
                : i,
            ),
      );
      const token = auth.get();
      if (token) {
        api
          .updateCartItem(token, productId, quantity, variantId)
          .then((c) => setItems(fromCart(c)))
          .catch(() => reloadServer());
      }
    },
    [reloadServer],
  );

  const clear = useCallback(() => {
    setItems([]);
    const token = auth.get();
    if (token) api.clearCart(token).catch(() => {});
  }, []);

  const total = items.reduce((sum, i) => sum + unitPrice(i) * i.quantity, 0);

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
