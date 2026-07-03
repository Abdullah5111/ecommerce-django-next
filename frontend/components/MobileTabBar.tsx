"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart";
import { useWishlist } from "@/lib/useWishlist";
import { cn } from "@/lib/cn";

type Tab = { href: string; label: string; icon: React.ReactNode; badge?: number };

function Icon({ d }: { d: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export default function MobileTabBar() {
  const pathname = usePathname();
  const { items } = useCart();
  const { items: wish } = useWishlist();
  const cartCount = items.reduce((s, i) => s + i.quantity, 0);

  const tabs: Tab[] = [
    { href: "/", label: "Home", icon: <Icon d="M3 12l9-9 9 9M5 10v10h14V10" /> },
    { href: "/wishlist", label: "Wishlist", icon: <Icon d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 1 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78z" />, badge: wish.length },
    { href: "/cart", label: "Cart", icon: <Icon d="M6 6h15l-1.5 9h-12zM6 6L5 3H2M9 20a1 1 0 1 0 0 .01M18 20a1 1 0 1 0 0 .01" />, badge: cartCount },
    { href: "/account", label: "Account", icon: <Icon d="M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" /> },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-white border-t border-zinc-200 flex">
      {tabs.map((tab) => {
        const active = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "relative flex-1 flex flex-col items-center gap-0.5 py-2 text-[11px]",
              active ? "text-brand" : "text-zinc-500",
            )}
          >
            <span className="relative">
              {tab.icon}
              {!!tab.badge && tab.badge > 0 && (
                <span className="absolute -top-1.5 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-brand text-brand-fg text-[10px] font-semibold flex items-center justify-center">
                  {tab.badge > 9 ? "9+" : tab.badge}
                </span>
              )}
            </span>
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
