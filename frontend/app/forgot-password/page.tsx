"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const res = await api.forgotPassword(email);
      setMessage(res.detail || "If that email exists, a reset link was sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto">
      <h1 className="text-2xl font-bold mb-6">Forgot password</h1>
      <form onSubmit={submit} className="space-y-4">
        <input
          className="w-full border rounded p-3"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <button
          disabled={loading}
          className="w-full bg-black text-white py-3 rounded font-medium disabled:opacity-60"
        >
          {loading ? "Sending…" : "Send reset link"}
        </button>
      </form>
      {message && <p className="text-zinc-700 mt-4 text-sm">{message}</p>}
      {error && <p className="text-red-600 mt-4 text-sm">{error}</p>}
      <p className="mt-6 text-sm">
        <Link href="/login" className="underline">Back to login</Link>
      </p>
    </div>
  );
}
