"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { Product } from "./api";

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

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  useEffect(() => {
    const raw = window.localStorage.getItem(KEY);
    if (raw) setItems(JSON.parse(raw));
  }, []);

  useEffect(() => {
    window.localStorage.setItem(KEY, JSON.stringify(items));
  }, [items]);

  const add = (product: Product, quantity = 1) =>
    setItems((prev) => {
      const existing = prev.find((i) => i.product.id === product.id);
      if (existing) {
        return prev.map((i) =>
          i.product.id === product.id ? { ...i, quantity: i.quantity + quantity } : i,
        );
      }
      return [...prev, { product, quantity }];
    });

  const remove = (productId: number) =>
    setItems((prev) => prev.filter((i) => i.product.id !== productId));

  const update = (productId: number, quantity: number) =>
    setItems((prev) =>
      quantity <= 0
        ? prev.filter((i) => i.product.id !== productId)
        : prev.map((i) => (i.product.id === productId ? { ...i, quantity } : i)),
    );

  const clear = () => setItems([]);

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
