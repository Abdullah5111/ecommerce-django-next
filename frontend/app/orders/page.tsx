"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Order } from "@/lib/api";
import { auth } from "@/lib/auth";

const STATUS_STYLES: Record<Order["status"], string> = {
  pending: "bg-yellow-100 text-yellow-800",
  paid: "bg-blue-100 text-blue-800",
  shipped: "bg-indigo-100 text-indigo-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-zinc-200 text-zinc-700",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

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
        <p className="text-zinc-500">Loading…</p>
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className="text-center py-20">
        <h1 className="text-2xl font-semibold">No orders yet</h1>
        <p className="text-zinc-500 mt-2">When you place your first order, it'll show up here.</p>
        <Link href="/" className="text-blue-600 underline mt-4 inline-block">
          Browse products
        </Link>
      </div>
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
                <div className="font-semibold">Order #{order.id}</div>
                <div className="text-sm text-zinc-500">{formatDate(order.created_at)}</div>
              </div>
              <span
                className={`text-xs font-medium px-2 py-1 rounded-full uppercase ${STATUS_STYLES[order.status]}`}
              >
                {order.status}
              </span>
            </div>

            <ul className="divide-y border-y">
              {order.items.map((item) => (
                <li key={item.id} className="py-2 flex justify-between text-sm">
                  <span>
                    {item.product_name} × {item.quantity}
                  </span>
                  <span className="text-zinc-700">${item.subtotal}</span>
                </li>
              ))}
            </ul>

            <div className="flex justify-between items-center mt-3">
              <span className="text-sm text-zinc-500 truncate max-w-xs">
                Ship to: {order.shipping_address}
              </span>
              <span className="font-semibold">Total ${order.total}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
