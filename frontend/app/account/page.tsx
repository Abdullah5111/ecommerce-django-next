"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Me } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";
import Avatar from "@/components/Avatar";
import AccountCard from "@/components/AccountCard";

export default function AccountHubPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login?next=/account");
    }
  }, [loading, user, router]);

  useEffect(() => {
    const token = auth.get();
    if (!user || !token) return;
    api
      .me(token)
      .then(setMe)
      .catch(() => {
        /* greeting falls back to context user */
      });
  }, [user]);

  if (loading || !user) {
    return <p className="text-zinc-600">Loading…</p>;
  }

  const greetingName = me?.display_name || me?.first_name || user.username;

  return (
    <div>
      <div className="flex items-center gap-4 mb-8">
        <Avatar src={me?.avatar ?? null} name={greetingName} size={64} />
        <div>
          <h1 className="text-2xl font-bold">Hello, {greetingName}</h1>
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <span>{user.email}</span>
            {user.email_verified ? (
              <span className="text-xs px-2 py-0.5 rounded bg-green-100 text-green-800 border border-green-200">
                Verified
              </span>
            ) : (
              <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
                Not verified
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <AccountCard
          href="/account/profile"
          icon="👤"
          title="Login & profile"
          subtitle="Photo, name, phone, and details"
        />
        <AccountCard
          href="/orders"
          icon="📦"
          title="Your orders"
          subtitle="Track, return, or buy again"
        />
        <AccountCard
          href="/account/addresses"
          icon="📍"
          title="Addresses"
          subtitle="Shipping and billing addresses"
        />
        <AccountCard
          href="/wishlist"
          icon="❤️"
          title="Wishlist"
          subtitle="Items you've saved for later"
        />
        <AccountCard
          href="/account/security"
          icon="🔒"
          title="Login & security"
          subtitle="Email, password, and phone"
        />
        <AccountCard
          href="/account/payment"
          icon="💳"
          title="Payment methods"
          subtitle="Manage cards and balance"
        />
        <AccountCard
          href="/account/notifications"
          icon="🔔"
          title="Communication preferences"
          subtitle="Emails and order alerts"
        />
      </div>
    </div>
  );
}
