"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const onHub = pathname === "/account";

  return (
    <div className="max-w-3xl mx-auto">
      {!onHub && (
        <Link
          href="/account"
          className="inline-block text-sm text-zinc-500 hover:text-zinc-900 mb-4"
        >
          ← Account
        </Link>
      )}
      {children}
    </div>
  );
}
