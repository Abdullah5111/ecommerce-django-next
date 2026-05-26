"use client";

import Link from "next/link";
import { useCart } from "@/lib/cart";

export default function Header() {
  const { items } = useCart();
  const count = items.reduce((s, i) => s + i.quantity, 0);
  return (
    <header className="border-b bg-white">
      <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold tracking-tight">
          shop.
        </Link>
        <nav className="flex items-center gap-6 text-sm">
          <Link href="/" className="hover:underline">Products</Link>
          <Link href="/cart" className="hover:underline">
            Cart {count > 0 && <span className="ml-1 bg-black text-white rounded-full px-2 text-xs">{count}</span>}
          </Link>
          <Link href="/login" className="hover:underline">Login</Link>
        </nav>
      </div>
    </header>
  );
}
