"use client";

import Loading from "@/components/ui/Loading";

import { buttonClasses } from "@/components/ui/Button";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SavedCards } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";
import { useToast } from "@/lib/useToast";
import AddCardForm from "@/components/AddCardForm";
import EmptyState from "@/components/EmptyState";
import { cardLabel, cardExpiry, isExpired } from "@/lib/cards";

export default function PaymentPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { toast } = useToast();

  const [data, setData] = useState<SavedCards | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Client secret of the SetupIntent behind the open "add card" form.
  const [setupSecret, setSetupSecret] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.push("/login?next=/account/payment");
  }, [authLoading, user, router]);

  const load = async () => {
    const token = auth.get();
    if (!token) return;
    try {
      setData(await api.listSavedCards(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load saved cards");
    }
  };

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const startAdding = async () => {
    const token = auth.get();
    if (!token) return;
    setStarting(true);
    try {
      const { client_secret } = await api.createCardSetupIntent(token);
      setSetupSecret(client_secret);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Couldn't start adding a card", "error");
    } finally {
      setStarting(false);
    }
  };

  const handleSaved = async () => {
    setSetupSecret(null);
    toast("Card saved", "success");
    await load();
  };

  const handleRemove = async (id: string) => {
    if (!window.confirm("Remove this card?")) return;
    const token = auth.get();
    if (!token) return;
    try {
      await api.removeSavedCard(token, id);
      toast("Card removed", "success");
      await load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to remove card", "error");
    }
  };

  if (authLoading || !user || (!data && !error)) return <Loading />;

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">Payment methods</h1>

      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      {data && !data.enabled && (
        <EmptyState
          icon="💳"
          title="Saved cards aren't available here"
          message="This store is running in demo payment mode, so there's nowhere to keep cards. Checkout still works."
        />
      )}

      {data?.enabled && (
        <>
          <div className="mb-6">
            {setupSecret ? (
              <div className="rounded-xl border border-zinc-200 bg-white p-4">
                <AddCardForm
                  publishableKey={data.publishable_key}
                  clientSecret={setupSecret}
                  onSaved={handleSaved}
                  onCancel={() => setSetupSecret(null)}
                />
              </div>
            ) : (
              <button
                onClick={startAdding}
                disabled={starting}
                className={buttonClasses("primary", "sm")}
              >
                {starting ? "Starting…" : "Add a card"}
              </button>
            )}
          </div>

          {data.cards.length === 0 ? (
            <EmptyState
              icon="💳"
              title="No saved cards"
              message="Cards you save here are stored by Stripe, not on our servers."
            />
          ) : (
            <ul className="space-y-3">
              {data.cards.map((card) => (
                <li
                  key={card.id}
                  className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white p-4"
                >
                  <div>
                    <p className="font-medium">{cardLabel(card)}</p>
                    <p className={isExpired(card) ? "text-sm text-red-600" : "text-sm text-zinc-500"}>
                      {isExpired(card) ? "Expired " : "Expires "}
                      {cardExpiry(card)}
                    </p>
                  </div>
                  <button
                    onClick={() => handleRemove(card.id)}
                    className={buttonClasses("ghost", "sm")}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
