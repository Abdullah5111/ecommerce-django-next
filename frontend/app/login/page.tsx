"use client";

import { buttonClasses } from "@/components/ui/Button";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";
import GoogleSignInButton from "@/components/GoogleSignInButton";

function LoginForm() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();

  // Only same-site relative paths — "?next=//evil.com" must not redirect off-site.
  const rawNext = params.get("next") || "/";
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const { access, refresh: refreshToken } = await api.login(username, password);
      auth.set(access, refreshToken);
      await refresh();
      router.push(next);
    } catch (e) {
      setError("Invalid credentials");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto">
      <h1 className="text-2xl font-bold mb-6">Login</h1>
      <form onSubmit={submit} className="space-y-4">
        <input className="w-full border rounded p-3 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand" placeholder="Username or email" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input className="w-full border rounded p-3 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button disabled={busy} className={buttonClasses("primary", "md", "w-full")}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      {error && <p className="text-red-600 mt-4">{error}</p>}
      <GoogleSignInButton next={next} />
      <p className="mt-4 text-sm">
        <Link href="/forgot-password" className="underline text-zinc-600">Forgot password?</Link>
      </p>
      <p className="mt-2 text-sm">
        No account? <Link href="/signup" className="underline">Sign up</Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-sm mx-auto">
          <h1 className="text-2xl font-bold mb-6">Login</h1>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
