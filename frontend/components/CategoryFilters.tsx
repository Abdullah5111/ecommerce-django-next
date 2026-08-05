"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";

export default function CategoryFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const [minVal, setMinVal] = useState(params.get("priceMin") ?? "");
  const [maxVal, setMaxVal] = useState(params.get("priceMax") ?? "");
  const [error, setError] = useState("");

  useEffect(() => {
    setMinVal(params.get("priceMin") ?? "");
    setMaxVal(params.get("priceMax") ?? "");
    setError("");
  }, [params]);

  const inStock = params.get("inStock") === "true";

  const pushWith = (mutate: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(params.toString());
    mutate(next);
    const qs = next.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  };

  const applyPrice = (e: React.FormEvent) => {
    e.preventDefault();
    // Reject a reversed range up front — the backend would just return nothing,
    // which reads as "no products" rather than a bad filter.
    if (minVal && maxVal && Number(minVal) > Number(maxVal)) {
      setError("Min can’t be greater than max.");
      return;
    }
    setError("");
    pushWith((n) => {
      if (minVal) n.set("priceMin", minVal);
      else n.delete("priceMin");
      if (maxVal) n.set("priceMax", maxVal);
      else n.delete("priceMax");
    });
  };

  const toggleInStock = (e: React.ChangeEvent<HTMLInputElement>) => {
    pushWith((n) => {
      if (e.target.checked) n.set("inStock", "true");
      else n.delete("inStock");
    });
  };

  return (
    <aside className="border rounded bg-white p-4 text-sm">
      <form onSubmit={applyPrice} className="mb-6">
        <h3 className="font-medium mb-2">Price</h3>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            inputMode="decimal"
            value={minVal}
            onChange={(e) => setMinVal(e.target.value)}
            placeholder="Min"
            className="w-full border rounded px-2 py-1"
          />
          <span className="text-zinc-400">–</span>
          <input
            type="number"
            min={0}
            inputMode="decimal"
            value={maxVal}
            onChange={(e) => setMaxVal(e.target.value)}
            placeholder="Max"
            className="w-full border rounded px-2 py-1"
          />
        </div>
        <button
          type="submit"
          className="mt-2 w-full bg-black text-white rounded px-3 py-1.5 text-sm font-medium hover:bg-zinc-800"
        >
          Apply
        </button>
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      </form>

      <div>
        <h3 className="font-medium mb-2">Availability</h3>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={inStock}
            onChange={toggleInStock}
            className="rounded border-zinc-300"
          />
          <span>In stock only</span>
        </label>
      </div>
    </aside>
  );
}
