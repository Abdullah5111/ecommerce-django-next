"use client";

import Link from "next/link";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type ProductSuggestion } from "@/lib/api";
import { useDebouncedValue } from "@/lib/useDebouncedValue";

export default function SearchBar() {
  const router = useRouter();
  const params = useSearchParams();
  const pathname = usePathname();
  const boxRef = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState(params.get("search") ?? "");
  const [suggestions, setSuggestions] = useState<ProductSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  // Index of the keyboard-highlighted row; -1 means none (Enter runs the
  // full-text search instead of jumping to a product).
  const [active, setActive] = useState(-1);

  const debounced = useDebouncedValue(value.trim(), 200);

  useEffect(() => {
    if (debounced.length < 2) {
      setSuggestions([]);
      setLoading(false);
      return;
    }
    // Guard against out-of-order responses: a slow request for "sho" must not
    // overwrite a newer one for "shoes". `ignore` is flipped by cleanup when
    // `debounced` changes before this request resolves.
    let ignore = false;
    setLoading(true);
    setOpen(true);
    api
      .suggest(debounced)
      .then((rows) => {
        if (ignore) return;
        setSuggestions(rows);
        setActive(-1);
      })
      .catch(() => {
        if (!ignore) setSuggestions([]);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [debounced]);

  // Close the dropdown when focus/click leaves the search box.
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i <= 0 ? suggestions.length - 1 : i - 1));
    } else if (e.key === "Enter" && active >= 0) {
      // Let a highlighted suggestion win over submitting the search form.
      e.preventDefault();
      setOpen(false);
      router.push(`/products/${suggestions[active].slug}`);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setOpen(false);
    const q = value.trim();
    const next = new URLSearchParams(params.toString());
    if (q) next.set("search", q);
    else next.delete("search");
    const qs = next.toString();
    const onCategoryPage = pathname?.startsWith("/c/");
    const base = onCategoryPage ? pathname : "/";
    router.push(qs ? `${base}?${qs}` : base);
  };

  const showDropdown = open && debounced.length >= 2;

  return (
    <div ref={boxRef} className="relative mb-6">
      <form onSubmit={submit} className="flex gap-2">
        <input
          type="search"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Search products…"
          className="flex-1 border rounded px-4 py-2"
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls="search-suggestions"
          aria-activedescendant={active >= 0 ? `suggestion-${suggestions[active].id}` : undefined}
          aria-autocomplete="list"
          autoComplete="off"
        />
        <button type="submit" className="bg-black text-white px-5 py-2 rounded font-medium hover:bg-zinc-800">
          Search
        </button>
      </form>

      {showDropdown && (
        <ul
          id="search-suggestions"
          role="listbox"
          className="absolute z-20 left-0 right-0 mt-1 bg-white border rounded shadow-lg overflow-hidden"
        >
          {suggestions.length === 0 && (
            <li className="px-3 py-2 text-sm text-zinc-500">
              {loading ? "Searching…" : "No products found"}
            </li>
          )}
          {suggestions.map((s, i) => (
            <li key={s.id} id={`suggestion-${s.id}`} role="option" aria-selected={i === active}>
              <Link
                href={`/products/${s.slug}`}
                onClick={() => setOpen(false)}
                onMouseEnter={() => setActive(i)}
                className={`flex items-center gap-3 px-3 py-2 ${
                  i === active ? "bg-zinc-100" : "hover:bg-zinc-50"
                }`}
              >
                {s.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={s.image_url} alt="" className="w-10 h-10 object-cover rounded bg-zinc-100" />
                ) : (
                  <span className="w-10 h-10 rounded bg-zinc-100" />
                )}
                <span className="flex-1 text-sm truncate">{s.name}</span>
                <span className="text-sm text-zinc-500">${s.price}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
