"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type Order, type ReturnRequest, type ReturnReason } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";

const REASONS: { value: ReturnReason; label: string }[] = [
  { value: "defective", label: "Defective" },
  { value: "wrong_item", label: "Wrong item" },
  { value: "not_as_described", label: "Not as described" },
  { value: "no_longer_needed", label: "No longer needed" },
  { value: "other", label: "Other" },
];

export default function OrderDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const [order, setOrder] = useState<Order | null>(null);
  const [returns, setReturns] = useState<ReturnRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [returnQty, setReturnQty] = useState<Record<number, number>>({});
  const [returnReason, setReturnReason] = useState<Record<number, ReturnReason>>({});
  const [showReturnForm, setShowReturnForm] = useState(false);

  const load = async () => {
    const token = auth.get();
    if (!token) {
      router.push(`/login?next=/orders/${id}`);
      return;
    }
    setError(null);
    try {
      const o = await api.getOrder(token, id);
      setOrder(o);
      const r = await api.listReturns(token, id);
      setReturns(r.results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load order");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const cancel = async () => {
    const token = auth.get();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelOrder(token, id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancel failed");
    } finally {
      setBusy(false);
    }
  };

  const submitReturn = async () => {
    const token = auth.get();
    if (!token || !order) return;
    const lines = order.items
      .filter((i) => (returnQty[i.id] ?? 0) > 0)
      .map((i) => ({
        order_item: i.id,
        quantity: returnQty[i.id] as number,
        reason: returnReason[i.id] ?? ("other" as ReturnReason),
      }));
    if (lines.length === 0) {
      setError("Select at least one item to return");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createReturn(token, { order: id, lines });
      setShowReturnForm(false);
      setReturnQty({});
      setReturnReason({});
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Return request failed");
    } finally {
      setBusy(false);
    }
  };

  if (error && !order) return <p className="text-red-600 py-12">{error}</p>;
  if (!order) return <p className="text-zinc-500 py-12">Loading…</p>;

  const canCancel = order.status === "pending" || order.status === "paid";
  const canReturn = order.status === "delivered" || order.status === "partially_refunded";

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Order #{order.id}</h1>
        <span className="text-sm uppercase px-2 py-1 rounded bg-zinc-100">{order.status}</span>
      </div>

      {order.tracking_number && (
        <p className="text-sm">
          Tracking: <span className="font-medium">{order.tracking_carrier} {order.tracking_number}</span>
        </p>
      )}

      <section>
        <h2 className="font-semibold mb-2">Items</h2>
        <ul className="divide-y border-y">
          {order.items.map((it) => (
            <li key={it.id} className="py-2 flex justify-between text-sm">
              <span>
                {it.product_name}
                {it.variant_label && (
                  <span className="text-zinc-500"> ({it.variant_label})</span>
                )}
                {" "}× {it.quantity}
              </span>
              <span>${it.subtotal}</span>
            </li>
          ))}
        </ul>
        <div className="mt-2 text-sm space-y-1">
          <div className="flex justify-between"><span>Subtotal</span><span>${order.subtotal}</span></div>
          {Number(order.discount_total) > 0 && (
            <div className="flex justify-between text-green-700"><span>Discount</span><span>−${order.discount_total}</span></div>
          )}
          <div className="flex justify-between"><span>Shipping</span><span>{Number(order.shipping_total) === 0 ? "Free" : `$${order.shipping_total}`}</span></div>
          {Number(order.tax_total) > 0 && (
            <div className="flex justify-between"><span>Tax</span><span>${order.tax_total}</span></div>
          )}
          <div className="flex justify-between font-semibold border-t pt-1"><span>Total</span><span>${order.total}</span></div>
          {Number(order.refunded_total) > 0 && (
            <div className="flex justify-between text-rose-700"><span>Refunded</span><span>−${order.refunded_total}</span></div>
          )}
        </div>
      </section>

      <section>
        <h2 className="font-semibold mb-2">Timeline</h2>
        <ul className="space-y-1 text-sm">
          {order.events.map((ev) => (
            <li key={ev.id} className="flex justify-between">
              <span>{ev.message}</span>
              <span className="text-zinc-500">{formatDateTime(ev.created_at)}</span>
            </li>
          ))}
        </ul>
      </section>

      {returns.length > 0 && (
        <section>
          <h2 className="font-semibold mb-2">Returns</h2>
          <ul className="space-y-2 text-sm">
            {returns.map((r) => (
              <li key={r.id} className="border rounded p-3">
                <div className="flex justify-between">
                  <span>Return #{r.id} — <span className="uppercase">{r.status}</span></span>
                  {Number(r.refund_amount) > 0 && <span className="text-rose-700">${r.refund_amount}</span>}
                </div>
                <ul className="text-zinc-600 mt-1">
                  {r.lines.map((l) => (
                    <li key={l.id}>
                      {l.product_name}
                      {l.variant_label && <span className="text-zinc-500"> ({l.variant_label})</span>}
                      {" "}× {l.quantity} ({l.reason})
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex gap-3">
        {canCancel && (
          <button onClick={cancel} disabled={busy} className="border rounded px-4 py-2 text-sm disabled:opacity-50">
            {busy ? "…" : "Cancel order"}
          </button>
        )}
        {canReturn && !showReturnForm && (
          <button onClick={() => setShowReturnForm(true)} className="border rounded px-4 py-2 text-sm">
            Request return
          </button>
        )}
      </div>

      {showReturnForm && (
        <section className="border rounded p-4 space-y-3">
          <h2 className="font-semibold">Request a return</h2>
          {order.items.map((it) => (
            <div key={it.id} className="flex items-center gap-3 text-sm">
              <span className="flex-1">
                {it.product_name}
                {it.variant_label && <span className="text-zinc-500"> ({it.variant_label})</span>}
                {" "}(×{it.quantity})
              </span>
              <input
                type="number"
                min={0}
                max={it.quantity}
                value={returnQty[it.id] ?? 0}
                onChange={(e) => setReturnQty({ ...returnQty, [it.id]: Number(e.target.value) })}
                className="w-16 border rounded px-2 py-1"
              />
              <select
                value={returnReason[it.id] ?? "other"}
                onChange={(e) => setReturnReason({ ...returnReason, [it.id]: e.target.value as ReturnReason })}
                className="border rounded px-2 py-1"
              >
                {REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
          ))}
          <div className="flex gap-2">
            <button onClick={submitReturn} disabled={busy} className="bg-black text-white rounded px-4 py-2 text-sm disabled:opacity-50">
              {busy ? "…" : "Submit return"}
            </button>
            <button onClick={() => setShowReturnForm(false)} className="border rounded px-4 py-2 text-sm">Cancel</button>
          </div>
        </section>
      )}

      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  );
}
