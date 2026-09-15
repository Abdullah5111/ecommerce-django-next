"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type StaffStats } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";

const STATUS_TONES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  paid: "bg-blue-100 text-blue-800",
  shipped: "bg-indigo-100 text-indigo-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-zinc-200 text-zinc-600",
  partially_refunded: "bg-orange-100 text-orange-800",
  refunded: "bg-rose-100 text-rose-800",
};

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="border rounded-xl p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function StaffDashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<StaffStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && (!user || !user.is_staff)) router.replace("/");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user?.is_staff) return;
    const token = auth.get();
    if (!token) return;
    api
      .getStaffStats(token)
      .then(setStats)
      .catch(() => setError("Couldn't load stats."));
  }, [user]);

  if (authLoading || !user?.is_staff) return <p className="text-zinc-600 py-12">Loading…</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Store overview</h1>
        <div className="flex gap-3 text-sm">
          <Link href="/staff/orders" className="text-brand hover:underline">
            Orders
          </Link>
          <Link href="/staff/chat" className="text-brand hover:underline">
            Inbox{stats && stats.open_chats > 0 ? ` (${stats.open_chats})` : ""}
          </Link>
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!stats ? (
        <p className="text-zinc-600 py-12">Loading…</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Tile label="Captured revenue" value={`$${Number(stats.revenue).toFixed(2)}`} sub="paid + shipped + delivered" />
            <Tile label="Paid orders" value={String(stats.paid_orders)} sub={`of ${stats.total_orders} total`} />
            <Tile label="Awaiting action" value={String((stats.orders_by_status.pending ?? 0) + (stats.orders_by_status.paid ?? 0))} sub="pending + paid" />
            <Tile label="Open chats" value={String(stats.open_chats)} sub="unread customer messages" />
          </div>

          <section className="grid gap-6 md:grid-cols-2">
            <div>
              <h2 className="font-semibold mb-2">Orders by status</h2>
              <ul className="border rounded-xl divide-y">
                {Object.entries(STATUS_TONES).map(([status, tone]) => (
                  <li key={status} className="px-4 py-2 flex items-center justify-between text-sm">
                    <span className={`px-2 py-0.5 rounded text-xs capitalize ${tone}`}>{status.replace("_", " ")}</span>
                    <span className="font-medium">{stats.orders_by_status[status] ?? 0}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h2 className="font-semibold mb-2">Low stock (≤ 5 left)</h2>
              {stats.low_stock.length === 0 ? (
                <p className="text-sm text-zinc-500 border rounded-xl p-4">Everything is well stocked.</p>
              ) : (
                <ul className="border rounded-xl divide-y">
                  {stats.low_stock.map((p) => (
                    <li key={p.id} className="px-4 py-2 flex items-center justify-between text-sm">
                      <Link href={`/products/${p.id}`} className="hover:underline truncate mr-3">
                        {p.name}
                      </Link>
                      <span className={`shrink-0 font-medium ${p.stock === 0 ? "text-rose-600" : "text-amber-700"}`}>
                        {p.stock} left
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
