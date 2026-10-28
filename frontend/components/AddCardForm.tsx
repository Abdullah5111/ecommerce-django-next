"use client";

import { buttonClasses } from "@/components/ui/Button";

import { useMemo, useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";

/** Saves a card against a SetupIntent — no charge. Cards resolve inline
 * (`redirect: "if_required"`); 3-D Secure opens Stripe's own modal. */
function SetupForm({ onSaved, onCancel }: { onSaved: () => void; onCancel: () => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSave = async () => {
    if (!stripe || !elements) return;
    setBusy(true);
    setError(null);
    const { error: setupError } = await stripe.confirmSetup({
      elements,
      redirect: "if_required",
      confirmParams: { return_url: window.location.href },
    });
    setBusy(false);
    if (setupError) {
      setError(setupError.message ?? "Couldn't save the card");
      return;
    }
    onSaved();
  };

  return (
    <div className="space-y-4">
      <PaymentElement />
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={!stripe || busy}
          className={buttonClasses("primary", "sm")}
        >
          {busy ? "Saving…" : "Save card"}
        </button>
        <button onClick={onCancel} disabled={busy} className={buttonClasses("ghost", "sm")}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function AddCardForm({
  publishableKey,
  clientSecret,
  onSaved,
  onCancel,
}: {
  publishableKey: string;
  clientSecret: string;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const stripePromise = useMemo(() => loadStripe(publishableKey), [publishableKey]);
  return (
    <Elements stripe={stripePromise} options={{ clientSecret }}>
      <SetupForm onSaved={onSaved} onCancel={onCancel} />
    </Elements>
  );
}
