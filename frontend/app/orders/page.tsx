"use client";

import Loading from "@/components/ui/Loading";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Order } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatDateTime, formatMoney } from "@/lib/format";
import EmptyState from "@/components/EmptyState";
import OrderStatusBadge from "@/components/ui/OrderStatusBadge";

export default function OrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = auth.get();
    if (!token) {
      router.push("/login?next=/orders");
      return;
    }
    api
      .listOrders(token)
      .then((data) => setOrders(data.results))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load orders"));
  }, [router]);

  if (error) {
    return (
      <div className="py-12">
        <h1 className="text-2xl font-bold mb-2">Your orders</h1>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  if (orders === null) {
    return (
      <div className="py-12">
        <h1 className="text-2xl font-bold mb-6">Your orders</h1>
        <Loading />
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <EmptyState
        icon={
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 2l1.5 3h9L18 2M3 6h18l-1.5 13.5a2 2 0 0 1-2 1.5H6.5a2 2 0 0 1-2-1.5zM9 11h6" /></svg>
        }
        title="No orders yet"
        message="When you place your first order, it'll show up here with live status."
        ctaHref="/"
        ctaLabel="Browse products"
      />
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Your orders</h1>
      <div className="space-y-4">
        {orders.map((order) => (
          <div key={order.id} className="bg-white border rounded-lg p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <Link href={`/orders/${order.id}`} className="font-semibold hover:underline">
                  Order #{order.id}
                </Link>
                <div className="text-sm text-zinc-500">{formatDateTime(order.created_at)}</div>
              </div>
              <OrderStatusBadge status={order.status} />
            </div>

            <ul className="divide-y border-y">
              {order.items.map((item) => (
                <li key={item.id} className="py-2 flex justify-between text-sm">
                  <span>
                    {item.product_name} × {item.quantity}
                  </span>
                  <span className="text-zinc-700">{formatMoney(item.subtotal)}</span>
                </li>
              ))}
            </ul>

            <div className="flex justify-between items-start mt-3 gap-4">
              <div className="text-sm text-zinc-500 max-w-xs">
                <div className="font-medium text-zinc-600">Ship to</div>
                {order.ship_recipient ? (
                  <div className="space-y-0.5">
                    <div>{order.ship_recipient}</div>
                    <div>{order.ship_line1}</div>
                    {order.ship_line2 && <div>{order.ship_line2}</div>}
                    <div>
                      {[order.ship_city, order.ship_state].filter(Boolean).join(", ")}
                      {order.ship_postal_code ? ` ${order.ship_postal_code}` : ""}
                    </div>
                    {order.ship_country && <div>{order.ship_country}</div>}
                    {order.ship_phone && <div>{order.ship_phone}</div>}
                  </div>
                ) : (
                  <div className="truncate">{order.shipping_address}</div>
                )}
              </div>
              <div className="text-sm text-right whitespace-nowrap">
                <div className="flex justify-end gap-6">
                  <span className="text-zinc-500">Subtotal</span>
                  <span>{formatMoney(order.subtotal)}</span>
                </div>
                {Number(order.discount_total) > 0 && (
                  <div className="flex justify-end gap-6 text-green-700">
                    <span>Discount{order.coupon_code ? ` (${order.coupon_code})` : ""}</span>
                    <span>−{formatMoney(order.discount_total)}</span>
                  </div>
                )}
                <div className="flex justify-end gap-6">
                  <span className="text-zinc-500">Shipping</span>
                  <span>{formatMoney(order.shipping_total, "Free")}</span>
                </div>
                <div className="flex justify-end gap-6 font-semibold border-t mt-1 pt-1">
                  <span>Total</span>
                  <span>{formatMoney(order.total)}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
