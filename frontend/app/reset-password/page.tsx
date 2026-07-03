"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function ResetPasswordForm() {
  const params = useSearchParams();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";

  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirm) {
      setError("Passwords don't match");
      return;
    }
    if (!uid || !token) {
      setError("Invalid reset link");
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(uid, token, newPassword);
      setSuccess(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Reset failed";
      // try to extract a cleaner detail from the API error string
      const match = msg.match(/API \d+: (.+)$/);
      if (match) {
        try {
          const parsed = JSON.parse(match[1]);
          if (parsed.detail) setError(parsed.detail);
          else if (parsed.new_password) setError(parsed.new_password.join(" "));
          else setError(msg);
        } catch {
          setError(msg);
        }
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="max-w-sm mx-auto">
        <h1 className="text-2xl font-bold mb-4">Password reset</h1>
        <p className="text-zinc-700 mb-6">Password reset — sign in.</p>
        <Link href="/login" className="underline">Go to login</Link>
      </div>
    );
  }

  return (
    <div className="max-w-sm mx-auto">
      <h1 className="text-2xl font-bold mb-6">Reset password</h1>
      <form onSubmit={submit} className="space-y-4">
        <input
          className="w-full border rounded p-3"
          type="password"
          placeholder="New password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
        />
        <input
          className="w-full border rounded p-3"
          type="password"
          placeholder="Confirm new password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
        <button
          disabled={loading}
          className="w-full bg-black text-white py-3 rounded font-medium disabled:opacity-60"
        >
          {loading ? "Resetting…" : "Reset password"}
        </button>
      </form>
      {error && <p className="text-red-600 mt-4 text-sm">{error}</p>}
      <p className="mt-6 text-sm">
        <Link href="/login" className="underline">Back to login</Link>
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-sm mx-auto">
          <h1 className="text-2xl font-bold mb-6">Reset password</h1>
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
