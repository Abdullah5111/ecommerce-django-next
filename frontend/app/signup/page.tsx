"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";

function Hint({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className={`flex items-center gap-2 ${ok ? "text-green-700" : "text-zinc-500"}`}>
      <span className="inline-block w-4">{ok ? "✓" : "✗"}</span>
      <span>{label}</span>
    </li>
  );
}

export default function SignupPage() {
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const { refresh } = useAuth();

  const pw = form.password;
  const longEnough = pw.length >= 8;
  const hasLetterAndDigit = /[A-Za-z]/.test(pw) && /\d/.test(pw);
  const notAllNumeric = pw.length > 0 && !/^\d+$/.test(pw);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.register(form);
      const { access, refresh: refreshToken } = await api.login(form.username, form.password);
      auth.set(access, refreshToken);
      await refresh();
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Signup failed");
    }
  };

  return (
    <div className="max-w-sm mx-auto">
      <h1 className="text-2xl font-bold mb-6">Create account</h1>
      <form onSubmit={submit} className="space-y-4">
        <input className="w-full border rounded p-3" placeholder="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <input className="w-full border rounded p-3" type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input className="w-full border rounded p-3" type="password" placeholder="Password (min 8 chars)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <ul className="text-xs space-y-1 pl-1">
          <Hint ok={longEnough} label="At least 8 characters" />
          <Hint ok={hasLetterAndDigit} label="Includes a letter and a digit" />
          <Hint ok={notAllNumeric} label="Not all numeric" />
        </ul>
        <button className="w-full bg-black text-white py-3 rounded font-medium">Sign up</button>
      </form>
      {error && <p className="text-red-600 mt-4">{error}</p>}
    </div>
  );
}
