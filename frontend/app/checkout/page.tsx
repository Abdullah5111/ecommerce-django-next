"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCart } from "@/lib/cart";
import { auth } from "@/lib/auth";
import { api } from "@/lib/api";

export default function CheckoutPage() {
  const { items, total, clear } = useCart();
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const placeOrder = async () => {
    setError(null);
    const token = auth.get();
    if (!token) {
      router.push("/login?next=/checkout");
      return;
    }
    setLoading(true);
    try {
      const order = await api.createOrder(token, {
        shipping_address: address,
        items: items.map((i) => ({ product: i.product.id, quantity: i.quantity })),
      });
      await api.payOrder(token, order.id);
      clear();
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold mb-6">Checkout</h1>
      <label className="block mb-2 text-sm font-medium">Shipping address</label>
      <textarea
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        rows={4}
        className="w-full border rounded p-3"
        placeholder="Street, city, ZIP, country"
      />
      <div className="mt-6 flex justify-between text-lg font-semibold">
        <span>Total</span>
        <span>${total.toFixed(2)}</span>
      </div>
      <button
        onClick={placeOrder}
        disabled={!address || items.length === 0 || loading}
        className="mt-6 w-full bg-black text-white py-3 rounded font-medium disabled:opacity-50"
      >
        {loading ? "Placing order…" : "Place order (mock payment)"}
      </button>
      {error && <p className="text-red-600 mt-4">{error}</p>}
    </div>
  );
}
