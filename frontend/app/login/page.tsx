"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const { refresh } = useAuth();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const { access, refresh: refreshToken } = await api.login(username, password);
      auth.set(access, refreshToken);
      await refresh();
      router.push(next);
    } catch (e) {
      setError("Invalid credentials");
    }
  };

  return (
    <div className="max-w-sm mx-auto">
      <h1 className="text-2xl font-bold mb-6">Login</h1>
      <form onSubmit={submit} className="space-y-4">
        <input className="w-full border rounded p-3" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input className="w-full border rounded p-3" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="w-full bg-black text-white py-3 rounded font-medium">Sign in</button>
      </form>
      {error && <p className="text-red-600 mt-4">{error}</p>}
      <p className="mt-6 text-sm">
        No account? <Link href="/signup" className="underline">Sign up</Link>
      </p>
    </div>
  );
}
