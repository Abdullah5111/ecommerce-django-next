"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type Address, type AddressInput } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";
import { useToast } from "@/lib/useToast";
import AddressForm from "@/components/AddressForm";

function formatAddress(a: Address) {
  const lines: string[] = [];
  lines.push(a.line1);
  if (a.line2) lines.push(a.line2);
  const cityLine = [a.city, a.state].filter(Boolean).join(", ");
  const cityState = [cityLine, a.postal_code].filter(Boolean).join(" ");
  if (cityState) lines.push(cityState);
  if (a.country) lines.push(a.country);
  if (a.phone) lines.push(a.phone);
  return lines;
}

export default function AddressesPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { toast } = useToast();

  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login?next=/account/addresses");
    }
  }, [authLoading, user, router]);

  const load = async () => {
    const token = auth.get();
    if (!token) return;
    try {
      const data = await api.listAddresses(token);
      setAddresses(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load addresses");
    }
  };

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const handleCreate = async (input: AddressInput) => {
    const token = auth.get();
    if (!token) return;
    try {
      await api.createAddress(token, input);
      toast("Address added", "success");
      setAdding(false);
      await load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to add address", "error");
    }
  };

  const handleUpdate = async (id: number, input: AddressInput) => {
    const token = auth.get();
    if (!token) return;
    try {
      await api.updateAddress(token, id, input);
      toast("Address updated", "success");
      setEditingId(null);
      await load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to update address", "error");
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Delete this address?")) return;
    const token = auth.get();
    if (!token) return;
    try {
      await api.deleteAddress(token, id);
      toast("Address deleted", "success");
      await load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to delete address", "error");
    }
  };

  const handleSetDefault = async (id: number) => {
    const token = auth.get();
    if (!token) return;
    try {
      await api.setDefaultAddress(token, id);
      toast("Default address updated", "success");
      await load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to set default", "error");
    }
  };

  if (authLoading || !user) {
    return <p className="text-zinc-600">Loading…</p>;
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Saved addresses</h1>
        <Link href="/account" className="text-sm text-zinc-600 hover:underline">
          ← Back to account
        </Link>
      </div>

      <div className="mb-6">
        {!adding ? (
          <button
            onClick={() => {
              setAdding(true);
              setEditingId(null);
            }}
            className="bg-black text-white py-2 px-4 rounded text-sm font-medium"
          >
            Add new address
          </button>
        ) : (
          <AddressForm
            submitLabel="Save address"
            onSubmit={handleCreate}
            onCancel={() => setAdding(false)}
          />
        )}
      </div>

      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      {addresses === null ? (
        <p className="text-zinc-500 text-sm">Loading addresses…</p>
      ) : addresses.length === 0 ? (
        <div className="border border-dashed border-zinc-300 rounded p-8 text-center">
          <p className="text-zinc-500">No saved addresses yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {addresses.map((a) => (
            <div key={a.id} className="bg-white border border-zinc-200 rounded p-4">
              {editingId === a.id ? (
                <AddressForm
                  initial={{
                    label: a.label,
                    recipient: a.recipient,
                    phone: a.phone,
                    line1: a.line1,
                    line2: a.line2,
                    city: a.city,
                    state: a.state,
                    postal_code: a.postal_code,
                    country: a.country,
                    is_default_shipping: a.is_default_shipping,
                  }}
                  submitLabel="Save changes"
                  onSubmit={(input) => handleUpdate(a.id, input)}
                  onCancel={() => setEditingId(null)}
                />
              ) : (
                <>
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-semibold">
                        {a.recipient}
                        {a.label && (
                          <span className="ml-2 text-xs text-zinc-500 font-normal">
                            ({a.label})
                          </span>
                        )}
                      </div>
                    </div>
                    {a.is_default_shipping && (
                      <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-800 border border-green-200">
                        Default
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-zinc-600 space-y-0.5">
                    {formatAddress(a).map((line, i) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                  <div className="flex items-center gap-4 mt-3 text-sm">
                    <button
                      onClick={() => {
                        setEditingId(a.id);
                        setAdding(false);
                      }}
                      className="text-zinc-700 hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(a.id)}
                      className="text-red-600 hover:underline"
                    >
                      Delete
                    </button>
                    {!a.is_default_shipping && (
                      <button
                        onClick={() => handleSetDefault(a.id)}
                        className="text-blue-600 hover:underline"
                      >
                        Set as default
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
