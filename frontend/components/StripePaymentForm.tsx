"use client";

import { useMemo, useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from "@stripe/react-stripe-js";

/**
 * Real-Stripe card form. Rendered only when the backend returns a live
 * PaymentIntent (keys configured). Confirms the payment with Stripe.js using
 * `redirect: "if_required"` so card payments resolve inline without a redirect,
 * then hands control back to checkout via `onPaid`.
 */
function CardForm({
  onPaid,
  amountLabel,
}: {
  onPaid: () => Promise<void>;
  amountLabel: string;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handlePay = async () => {
    if (!stripe || !elements) return;
    setBusy(true);
    setError(null);
    const { error: confirmError } = await stripe.confirmPayment({
      elements,
      redirect: "if_required",
    });
    if (confirmError) {
      setError(confirmError.message ?? "Payment failed");
      setBusy(false);
      return;
    }
    // Charge succeeded — let checkout finalize the order (backend verifies the
    // intent; the webhook is the authoritative backstop).
    await onPaid();
    setBusy(false);
  };

  return (
    <div className="space-y-4">
      <PaymentElement />
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <button
        onClick={handlePay}
        disabled={!stripe || busy}
        className="w-full bg-black text-white py-3 rounded font-medium disabled:opacity-50"
      >
        {busy ? "Processing…" : `Pay ${amountLabel}`}
      </button>
    </div>
  );
}

export default function StripePaymentForm({
  publishableKey,
  clientSecret,
  amountLabel,
  onPaid,
}: {
  publishableKey: string;
  clientSecret: string;
  amountLabel: string;
  onPaid: () => Promise<void>;
}) {
  const stripePromise = useMemo(
    () => loadStripe(publishableKey),
    [publishableKey],
  );

  return (
    <Elements stripe={stripePromise} options={{ clientSecret }}>
      <CardForm onPaid={onPaid} amountLabel={amountLabel} />
    </Elements>
  );
}
