"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";

export default function AccountPage() {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
  });
  const [fetching, setFetching] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedVisible, setSavedVisible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addressCount, setAddressCount] = useState<number | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login?next=/account");
    }
  }, [loading, user, router]);

  useEffect(() => {
    const load = async () => {
      const token = auth.get();
      if (!token) return;
      try {
        const me = await api.me(token);
        setForm({
          first_name: me.first_name || "",
          last_name: me.last_name || "",
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setFetching(false);
      }
      try {
        const list = await api.listAddresses(token);
        setAddressCount(list.length);
      } catch {
        // non-fatal — leave count unknown
      }
    };
    if (user) load();
  }, [user]);

  useEffect(() => {
    if (!savedVisible) return;
    const t = setTimeout(() => setSavedVisible(false), 1800);
    return () => clearTimeout(t);
  }, [savedVisible]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const token = auth.get();
    if (!token) return;
    setSaving(true);
    try {
      await api.updateMe(token, form);
      await refresh();
      setSavedVisible(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !user) {
    return <p className="text-zinc-600">Loading…</p>;
  }

  const addressSummary =
    addressCount === null
      ? "Manage your shipping addresses"
      : addressCount === 0
        ? "No saved addresses yet"
        : `${addressCount} saved address${addressCount === 1 ? "" : "es"}`;

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-6">Account</h1>

      <div className="border rounded p-4 mb-6 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-500">Username</span>
          <span className="font-medium">{user.username}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-500">Email</span>
          <span className="font-medium">{user.email}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-500">Status</span>
          {user.email_verified ? (
            <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-800 border border-green-200">
              Verified
            </span>
          ) : (
            <span className="text-xs px-2 py-1 rounded bg-amber-100 text-amber-800 border border-amber-200">
              Not verified
            </span>
          )}
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-3">Profile</h2>
      {fetching ? (
        <p className="text-zinc-600 text-sm">Loading profile…</p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <input
              className="w-full border rounded p-3"
              placeholder="First name"
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            />
            <input
              className="w-full border rounded p-3"
              placeholder="Last name"
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              disabled={saving}
              className="bg-black text-white py-2 px-4 rounded font-medium disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <span
              className={`text-sm text-green-700 transition-opacity duration-500 ${
                savedVisible ? "opacity-100" : "opacity-0"
              }`}
            >
              Saved
            </span>
          </div>
        </form>
      )}
      {error && <p className="text-red-600 mt-4 text-sm">{error}</p>}

      <h2 className="text-lg font-semibold mt-8 mb-3">Addresses</h2>
      <Link
        href="/account/addresses"
        className="block bg-white border border-zinc-200 rounded p-4 hover:border-zinc-400 transition-colors"
      >
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">Saved addresses</div>
            <div className="text-sm text-zinc-500">{addressSummary}</div>
          </div>
          <span className="text-zinc-400">→</span>
        </div>
      </Link>

      <p className="mt-8 text-sm">
        <Link href="/forgot-password" className="underline text-zinc-600">
          Change password
        </Link>
      </p>
    </div>
  );
}
