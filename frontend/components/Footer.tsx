import Link from "next/link";

const COLUMNS: { title: string; links: { label: string; href: string }[] }[] = [
  {
    title: "Shop",
    links: [
      { label: "All products", href: "/" },
      { label: "Wishlist", href: "/wishlist" },
      { label: "Cart", href: "/cart" },
    ],
  },
  {
    title: "Account",
    links: [
      { label: "Your account", href: "/account" },
      { label: "Orders", href: "/orders" },
      { label: "Addresses", href: "/account/addresses" },
      { label: "Notifications", href: "/account/notifications" },
    ],
  },
  {
    title: "Help",
    links: [
      { label: "Returns", href: "/orders" },
      { label: "Sign in", href: "/login" },
      { label: "Create account", href: "/signup" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-zinc-200 bg-white">
      <div className="max-w-6xl mx-auto px-4 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="col-span-2 md:col-span-1">
            <div className="text-xl font-bold tracking-tight">shop.</div>
            <p className="mt-2 text-sm text-zinc-500 max-w-xs">
              A modern storefront — fast shipping, easy returns, and secure checkout.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <div key={col.title}>
              <h3 className="text-sm font-semibold mb-3">{col.title}</h3>
              <ul className="space-y-2">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <Link href={link.href} className="text-sm text-zinc-600 hover:text-brand">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 pt-6 border-t border-zinc-100 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-zinc-500">
          <span>© {new Date().getFullYear()} shop. All rights reserved.</span>
          <span className="flex items-center gap-2">
            <span className="rounded border border-zinc-200 px-2 py-0.5">Visa</span>
            <span className="rounded border border-zinc-200 px-2 py-0.5">Mastercard</span>
            <span className="rounded border border-zinc-200 px-2 py-0.5">Amex</span>
          </span>
        </div>
      </div>
    </footer>
  );
}
