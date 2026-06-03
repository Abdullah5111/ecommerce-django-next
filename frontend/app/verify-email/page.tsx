"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

type State = "verifying" | "success" | "error";

export default function VerifyEmailPage() {
  const params = useSearchParams();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";
  const [state, setState] = useState<State>("verifying");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!uid || !token) {
        if (!cancelled) setState("error");
        return;
      }
      try {
        await api.verifyEmail(uid, token);
        if (!cancelled) setState("success");
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [uid, token]);

  return (
    <div className="max-w-sm mx-auto">
      <h1 className="text-2xl font-bold mb-6">Email verification</h1>
      {state === "verifying" && <p className="text-zinc-700">Verifying…</p>}
      {state === "success" && (
        <>
          <p className="text-green-700 mb-4">Email verified! ✓</p>
          <Link href="/" className="underline">Back to shop</Link>
        </>
      )}
      {state === "error" && (
        <>
          <p className="text-red-600 mb-4">Invalid or expired link.</p>
          <Link href="/" className="underline">Back to shop</Link>
        </>
      )}
    </div>
  );
}
