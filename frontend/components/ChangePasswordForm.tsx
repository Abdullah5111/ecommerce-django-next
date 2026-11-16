"use client";

import { buttonClasses } from "@/components/ui/Button";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fieldErrors } from "@/lib/apiErrors";
import { auth } from "@/lib/auth";

/** Change the password while signed in. The server signs out every other
 * session and hands this browser a fresh one, which is stored here. */
export default function ChangePasswordForm({
  onDone,
  onCancel,
}: {
  onDone: () => void;
  onCancel: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      setErrors({ confirm: "The new passwords don't match." });
      return;
    }
    const token = auth.get();
    if (!token) return;
    setBusy(true);
    setErrors({});
    try {
      const { access } = await api.changePassword(token, current, next);
      auth.set(access);
      onDone();
    } catch (err) {
      setErrors(fieldErrors(err));
    } finally {
      setBusy(false);
    }
  };

  const fieldError = (name: string) =>
    errors[name] ? (
      <p className="text-sm text-red-600 mt-1" role="alert">
        {errors[name]}
      </p>
    ) : null;

  return (
    <form onSubmit={submit} className="space-y-3 max-w-sm" aria-label="Change password">
      <div>
        <input
          className="w-full border rounded p-3"
          type="password"
          autoComplete="current-password"
          placeholder="Current password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        {fieldError("current_password")}
      </div>
      <div>
        <input
          className="w-full border rounded p-3"
          type="password"
          autoComplete="new-password"
          placeholder="New password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
        />
        {fieldError("new_password")}
      </div>
      <div>
        <input
          className="w-full border rounded p-3"
          type="password"
          autoComplete="new-password"
          placeholder="Confirm new password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
        {fieldError("confirm")}
      </div>
      {fieldError("detail")}
      <p className="text-xs text-zinc-500">
        You&apos;ll stay signed in here; other devices will be signed out.
      </p>
      <div className="flex gap-2 items-center">
        <button disabled={busy} className={buttonClasses("primary", "sm")}>
          {busy ? "Saving…" : "Change password"}
        </button>
        <button type="button" onClick={onCancel} className={buttonClasses("ghost", "sm")}>
          Cancel
        </button>
        <Link href="/forgot-password" className="text-sm underline text-zinc-600 ml-auto">
          Forgot your password?
        </Link>
      </div>
    </form>
  );
}
