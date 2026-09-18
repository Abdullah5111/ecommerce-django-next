"use client";

import { buttonClasses } from "@/components/ui/Button";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type Order } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { realtime } from "@/lib/realtime";
import { useAuth } from "@/lib/useAuth";
import { useToast } from "@/lib/useToast";
import OrderStatusBadge from "@/components/ui/OrderStatusBadge";

const ACTIONABLE = new Set(["pending", "paid", "shipped"]);

/** Staff order console: the ship/deliver buttons that drive the live demo. */
export default function StaffOrdersPage() {
  const { user, loading: authLoading } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>("active");
  const [tracking, setTracking] = useState<Record<number, string>>({});

  useEffect(() => {
    if (!authLoading && (!user || !user.is_staff)) router.replace("/");
  }, [authLoading, user, router]);

  const load = useCallback(async () => {
    const token = auth.get();
    if (!token) return;
    try {
      const page = await api.listOrders(token);
      setOrders(page.results);
      setNextPage(page.next ? 2 : null);
    } catch {
      setOrders([]);
      setNextPage(null);
    }
  }, []);

  const loadMore = async () => {
    const token = auth.get();
    if (!token || nextPage === null) return;
    try {
      const page = await api.listOrders(token, nextPage);
      setOrders((prev) => [...(prev ?? []), ...page.results]);
      setNextPage(page.next ? nextPage + 1 : null);
    } catch {
      toast("Couldn't load more orders", "error");
    }
  };

  useEffect(() => {
    if (!user?.is_staff) return;
    realtime.connect();
    load();
    return realtime.subscribe((msg) => {
      // keep the console fresh while staff work in it
      if (msg.type === "notification" || msg.type === "realtime.open") load();
    });
  }, [user, load]);

  const act = async (order: Order, fn: (t: string, id: number, extra?: object) => Promise<Order>, extra?: object) => {
    const token = auth.get();
    if (!token) return;
    setBusyId(order.id);
    try {
      const updated = await fn(token, order.id, extra);
      setOrders((prev) => prev?.map((o) => (o.id === updated.id ? updated : o)) ?? prev);
      toast(`Order #${order.id} updated`, "success");
    } catch {
      toast("Action failed — try again", "error");
    } finally {
      setBusyId(null);
    }
  };

  if (authLoading || !user?.is_staff) return <p className="text-zinc-600 py-12">Loading…</p>;

  const visible = (orders ?? []).filter((o) => {
    if (filter === "active") return ACTIONABLE.has(o.status);
    if (filter === "done") return o.status === "delivered";
    if (filter === "cancelled") return o.status === "cancelled" || o.status.endsWith("refunded");
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold">Orders</h1>
        <div className="flex gap-1 text-sm">
          {[
            ["active", "Needs action"],
            ["all", "All"],
            ["done", "Delivered"],
            ["cancelled", "Closed"],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-3 py-1 rounded-full border ${filter === key ? "bg-brand text-brand-fg border-brand" : "hover:bg-zinc-50"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {orders === null ? (
        <p className="text-zinc-600 py-12">Loading…</p>
      ) : visible.length === 0 ? (
        <p className="text-zinc-500 py-12 text-center">Nothing here.</p>
      ) : (
        <ul className="space-y-3">
          {visible.map((o) => {
            const busy = busyId === o.id;
            return (
              <li key={o.id} className="border rounded-xl p-4">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <p className="text-sm font-medium flex items-center gap-2 flex-wrap">
                      <Link href={`/orders/${o.id}`} className="hover:underline">
                        #{o.id}
                      </Link>
                      <OrderStatusBadge status={o.status} />
                      <span className="text-zinc-500 font-normal">
                        {o.username} · {formatDateTime(o.created_at)} · ${o.total}
                      </span>
                    </p>
                    <p className="text-xs text-zinc-500 truncate mt-0.5">
                      {o.items.map((i) => `${i.product_name} ×${i.quantity}`).join(", ")}
                    </p>
                    {o.status === "shipped" && (o.tracking_number || o.tracking_carrier) && (
                      <p className="text-xs text-zinc-500 mt-0.5">
                        Tracking: {o.tracking_carrier} {o.tracking_number}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {o.status === "paid" && (
                      <>
                        <input
                          value={tracking[o.id] ?? ""}
                          onChange={(e) => setTracking((t) => ({ ...t, [o.id]: e.target.value }))}
                          placeholder="Tracking # (optional)"
                          className="border rounded px-2 py-1 text-xs w-40"
                          aria-label={`Tracking number for order ${o.id}`}
                        />
                        <button
                          onClick={() => act(o, api.shipOrder, { tracking_number: tracking[o.id] ?? "" })}
                          disabled={busy}
                          className={buttonClasses("primary", "sm")}
                        >
                          {busy ? "…" : "Mark shipped"}
                        </button>
                      </>
                    )}
                    {o.status === "shipped" && (
                      <button
                        onClick={() => act(o, api.deliverOrder)}
                        disabled={busy}
                        className={buttonClasses("primary", "sm")}
                      >
                        {busy ? "…" : "Mark delivered"}
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {nextPage !== null && orders !== null && (
        <div className="text-center">
          <button onClick={loadMore} className="border rounded px-4 py-2 text-sm hover:bg-zinc-50">
            Load more
          </button>
        </div>
      )}
    </div>
  );
}
