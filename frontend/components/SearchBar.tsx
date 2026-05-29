"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

export default function SearchBar() {
  const router = useRouter();
  const params = useSearchParams();
  const [value, setValue] = useState(params.get("search") ?? "");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    router.push(q ? `/?search=${encodeURIComponent(q)}` : "/");
  };

  return (
    <form onSubmit={submit} className="flex gap-2 mb-6">
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search products…"
        className="flex-1 border rounded px-4 py-2"
      />
      <button type="submit" className="bg-black text-white px-5 py-2 rounded font-medium hover:bg-zinc-800">
        Search
      </button>
    </form>
  );
}
