"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCart } from "@/lib/cart";
import { useAuth } from "@/lib/useAuth";
import { useWishlist } from "@/lib/useWishlist";
import MegaMenu from "@/components/MegaMenu";
import NotificationBell from "@/components/NotificationBell";

export default function Header() {
  const { items } = useCart();
  const { items: wishItems } = useWishlist();
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const count = items.reduce((s, i) => s + i.quantity, 0);
  const wishCount = wishItems.length;

  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  return (
    <header className="border-b bg-white">
      <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold tracking-tight">
          shop.
        </Link>
        <nav className="flex items-center gap-6 text-sm">
          <div className="hidden md:block">
            <MegaMenu />
          </div>
          <Link href="/" className="md:hidden hover:underline">Shop</Link>
          <Link href="/orders" className="hover:underline">Orders</Link>
          <Link href="/wishlist" className="hover:underline inline-flex items-center gap-1" aria-label="Wishlist">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
            <span className="hidden sm:inline">Wishlist</span>
            {wishCount > 0 && <span className="ml-1 bg-black text-white rounded-full px-2 text-xs">{wishCount}</span>}
          </Link>
          <Link href="/cart" className="hover:underline">
            Cart {count > 0 && <span className="ml-1 bg-black text-white rounded-full px-2 text-xs">{count}</span>}
          </Link>
          {loading ? null : user ? (
            <div className="flex items-center gap-3">
              <NotificationBell />
              <Link href="/account" className="text-zinc-600 hover:underline">Hi, {user.username}</Link>
              <button
                onClick={handleLogout}
                className="hover:underline text-zinc-600"
              >
                Logout
              </button>
            </div>
          ) : (
            <Link href="/login" className="hover:underline">Login</Link>
          )}
        </nav>
      </div>
    </header>
  );
}
