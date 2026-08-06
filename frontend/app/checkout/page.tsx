"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useCart } from "@/lib/cart";
import { auth } from "@/lib/auth";
import { api, type Address, type AddressInput, type QuoteResult } from "@/lib/api";
import { useToast } from "@/lib/useToast";
import AddressForm from "@/components/AddressForm";
import StripePaymentForm from "@/components/StripePaymentForm";

type LivePayment = {
  orderId: number;
  clientSecret: string;
  publishableKey: string;
};

export default function CheckoutPage() {
  const { items, total, clear } = useCart();
  const router = useRouter();
  const { toast } = useToast();

  const [authed, setAuthed] = useState<boolean | null>(null);
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);

  const [guestAddress, setGuestAddress] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [payment, setPayment] = useState<LivePayment | null>(null);
  // Order already created but not yet paid — reused on retry so a failed
  // payment-start doesn't create a second stock-holding order.
  const [pendingOrderId, setPendingOrderId] = useState<number | null>(null);

  const [promoInput, setPromoInput] = useState("");
  const [appliedCode, setAppliedCode] = useState<string | null>(null);
  const [quote, setQuote] = useState<QuoteResult | null>(null);
  const [promoError, setPromoError] = useState<string | null>(null);
  const [quoting, setQuoting] = useState(false);

  useEffect(() => {
    const token = auth.get();
    if (!token) {
      setAuthed(false);
      return;
    }
    setAuthed(true);
    api
      .listAddresses(token)
      .then((list) => {
        setAddresses(list);
        const def = list.find((a) => a.is_default_shipping) ?? list[0];
        if (def) setSelectedId(def.id);
        if (list.length === 0) setShowNewForm(true);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load addresses");
        setAddresses([]);
      });
  }, []);

  const handleSaveNewAddress = async (input: AddressInput): Promise<Address | null> => {
    const token = auth.get();
    if (!token) return null;
    try {
      const created = await api.createAddress(token, input);
      toast("Address saved", "success");
      const next = addresses ? [...addresses, created] : [created];
      setAddresses(next);
      setSelectedId(created.id);
      setShowNewForm(false);
      return created;
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to save address", "error");
      return null;
    }
  };

  const refreshQuote = async (code?: string) => {
    const token = auth.get();
    if (!token || items.length === 0) return;
    setQuoting(true);
    setPromoError(null);
    try {
      const result = await api.quoteOrder(token, {
        code,
        items: items.map((i) => ({ product: i.product.id, variant: i.variant?.id ?? null, quantity: i.quantity })),
      });
      setQuote(result);
      if (code) {
        if (result.coupon_error) {
          setPromoError(result.coupon_error);
          setAppliedCode(null);
        } else {
          setAppliedCode(result.coupon_code);
        }
      }
    } catch (e) {
      setPromoError(e instanceof Error ? e.message : "Could not apply code");
    } finally {
      setQuoting(false);
    }
  };

  const applyPromo = () => {
    if (!promoInput.trim()) return;
    refreshQuote(promoInput.trim());
  };

  const removePromo = () => {
    setPromoInput("");
    setAppliedCode(null);
    setPromoError(null);
    refreshQuote();
  };

  useEffect(() => {
    if (authed && items.length > 0) {
      refreshQuote(appliedCode ?? undefined);
    }
    // Re-quote on auth/cart-size change only; appliedCode is excluded because
    // applyPromo/removePromo already re-quote, so including it would double-request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed, items.length]);

  // A changed cart, address, or coupon makes any existing pending order stale;
  // drop the reference so the next attempt creates a fresh one.
  useEffect(() => {
    setPendingOrderId(null);
  }, [items, selectedId, appliedCode]);

  // Confirm a paid order on the backend (after card confirm in live mode, immediately in mock).
  const finalizeOrder = async (orderId: number) => {
    const token = auth.get();
    if (!token) return;
    await api.payOrder(token, orderId);
    clear();
    toast("Order placed", "success");
    router.push("/");
  };

  // Kick off payment for a new order: mock confirms immediately, live surfaces the PaymentElement.
  const startPayment = async (token: string, orderId: number) => {
    const intent = await api.createPaymentIntent(token, orderId);
    if (intent.mock || !intent.publishable_key) {
      await finalizeOrder(orderId);
      return;
    }
    setPayment({
      orderId,
      clientSecret: intent.client_secret,
      publishableKey: intent.publishable_key,
    });
  };

  const placeOrder = async (overrideAddressId?: number) => {
    setError(null);
    const token = auth.get();

    if (!token) {
      if (!guestAddress.trim()) {
        setError("Please enter a shipping address");
        return;
      }
      router.push("/login?next=/checkout");
      return;
    }

    const addressId = overrideAddressId ?? selectedId;
    if (!addressId) {
      setError("Please select or add a shipping address");
      return;
    }

    setLoading(true);
    try {
      // Reuse the order from a prior attempt (e.g. payment-start failed) instead
      // of creating a duplicate; the reset effect clears it if the cart changed.
      let orderId = pendingOrderId;
      if (orderId == null) {
        const order = await api.createOrder(token, {
          shipping_address_id: addressId,
          items: items.map((i) => ({ product: i.product.id, variant: i.variant?.id ?? null, quantity: i.quantity })),
          coupon_code: appliedCode ?? undefined,
        });
        orderId = order.id;
        setPendingOrderId(orderId);
      }
      await startPayment(token, orderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setLoading(false);
    }
  };

  const placeGuestOrder = async () => {
    // Guests must log in — keep legacy text fallback in case backend ever supports it.
    setError(null);
    const token = auth.get();
    if (!token) {
      router.push("/login?next=/checkout");
      return;
    }
    setLoading(true);
    try {
      const order = await api.createOrder(token, {
        shipping_address: guestAddress,
        items: items.map((i) => ({ product: i.product.id, variant: i.variant?.id ?? null, quantity: i.quantity })),
      });
      await startPayment(token, order.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setLoading(false);
    }
  };

  if (authed === null) {
    return <p className="text-zinc-600">Loading…</p>;
  }

  if (payment) {
    const amountLabel = `$${quote ? quote.grand_total : total.toFixed(2)}`;
    return (
      <div className="max-w-lg">
        <h1 className="text-2xl font-bold mb-6">Payment</h1>
        <StripePaymentForm
          publishableKey={payment.publishableKey}
          clientSecret={payment.clientSecret}
          amountLabel={amountLabel}
          onPaid={() => finalizeOrder(payment.orderId)}
        />
        {error && <p className="text-red-600 mt-4">{error}</p>}
      </div>
    );
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold mb-6">Checkout</h1>

      <h2 className="text-base font-semibold mb-3">Shipping address</h2>

      {!authed ? (
        <>
          <textarea
            value={guestAddress}
            onChange={(e) => setGuestAddress(e.target.value)}
            rows={4}
            className="w-full border rounded p-3"
            placeholder="Street, city, ZIP, country"
          />
          <div className="mt-6 flex justify-between text-lg font-semibold">
            <span>Total</span>
            <span>${total.toFixed(2)}</span>
          </div>
          <button
            onClick={placeGuestOrder}
            disabled={!guestAddress || items.length === 0 || loading}
            className="mt-6 w-full bg-black text-white py-3 rounded font-medium disabled:opacity-50"
          >
            {loading ? "Placing order…" : "Place order"}
          </button>
        </>
      ) : addresses === null ? (
        <p className="text-zinc-500 text-sm">Loading addresses…</p>
      ) : (
        <>
          {addresses.length === 0 ? (
            <AddressForm
              submitLabel="Save & use this address"
              onSubmit={async (input) => {
                const created = await handleSaveNewAddress(input);
                if (created) await placeOrder(created.id);
              }}
            />
          ) : (
            <>
              <div className="space-y-2">
                {addresses.map((a) => (
                  <label
                    key={a.id}
                    className={`flex items-start gap-3 bg-white border rounded p-3 cursor-pointer ${
                      selectedId === a.id ? "border-black" : "border-zinc-200"
                    }`}
                  >
                    <input
                      type="radio"
                      className="mt-1"
                      name="shipping_address"
                      checked={selectedId === a.id}
                      onChange={() => setSelectedId(a.id)}
                    />
                    <div className="flex-1 text-sm">
                      <div className="font-medium">
                        {a.recipient}
                        {a.label && (
                          <span className="ml-2 text-xs text-zinc-500 font-normal">
                            ({a.label})
                          </span>
                        )}
                        {a.is_default_shipping && (
                          <span className="ml-2 text-xs px-2 py-0.5 rounded bg-green-100 text-green-800 border border-green-200">
                            Default
                          </span>
                        )}
                      </div>
                      <div className="text-zinc-600">
                        {a.line1}
                        {a.line2 ? `, ${a.line2}` : ""}, {a.city}
                        {a.state ? `, ${a.state}` : ""} {a.postal_code}, {a.country}
                      </div>
                    </div>
                  </label>
                ))}
              </div>

              {!showNewForm ? (
                <button
                  type="button"
                  onClick={() => setShowNewForm(true)}
                  className="mt-3 text-sm text-blue-600 hover:underline"
                >
                  Use a different address
                </button>
              ) : (
                <div className="mt-3">
                  <AddressForm
                    submitLabel="Save address"
                    onSubmit={async (input) => {
                      await handleSaveNewAddress(input);
                    }}
                    onCancel={() => setShowNewForm(false)}
                  />
                </div>
              )}

              <div className="mt-6 border-t pt-4">
                <label className="block text-sm font-medium mb-1">Promo code</label>
                <div className="flex gap-2">
                  <input
                    value={promoInput}
                    onChange={(e) => setPromoInput(e.target.value)}
                    placeholder="e.g. SAVE10"
                    className="flex-1 border rounded px-3 py-2 text-sm"
                    disabled={!!appliedCode}
                  />
                  {appliedCode ? (
                    <button
                      type="button"
                      onClick={removePromo}
                      className="px-4 py-2 text-sm border rounded"
                    >
                      Remove
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={applyPromo}
                      disabled={quoting || !promoInput.trim()}
                      className="px-4 py-2 text-sm border rounded disabled:opacity-50"
                    >
                      {quoting ? "…" : "Apply"}
                    </button>
                  )}
                </div>
                {promoError && <p className="text-red-600 text-sm mt-1">{promoError}</p>}
                {appliedCode && (
                  <p className="text-green-700 text-sm mt-1">Code {appliedCode} applied</p>
                )}
              </div>

              <div className="mt-4 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Subtotal</span>
                  <span>${quote ? quote.subtotal : total.toFixed(2)}</span>
                </div>
                {quote && Number(quote.discount_total) > 0 && (
                  <div className="flex justify-between text-green-700">
                    <span>Discount{appliedCode ? ` (${appliedCode})` : ""}</span>
                    <span>−${quote.discount_total}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Shipping</span>
                  <span>
                    {!quote
                      ? "—"
                      : Number(quote.shipping_total) === 0
                        ? "Free"
                        : `$${quote.shipping_total}`}
                  </span>
                </div>
                {quote && Number(quote.tax_total) > 0 && (
                  <div className="flex justify-between">
                    <span>Tax</span>
                    <span>${quote.tax_total}</span>
                  </div>
                )}
                <div className="flex justify-between text-lg font-semibold border-t pt-2 mt-2">
                  <span>Total</span>
                  <span>${quote ? quote.grand_total : total.toFixed(2)}</span>
                </div>
              </div>
              <button
                onClick={() => placeOrder()}
                disabled={!selectedId || items.length === 0 || loading}
                className="mt-6 w-full bg-black text-white py-3 rounded font-medium disabled:opacity-50"
              >
                {loading ? "Placing order…" : "Place order"}
              </button>
            </>
          )}
        </>
      )}

      {error && <p className="text-red-600 mt-4">{error}</p>}
    </div>
  );
}
