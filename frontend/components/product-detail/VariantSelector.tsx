"use client";

import { useMemo, useState } from "react";
import type { ProductVariant } from "@/lib/api";
import { cn } from "@/lib/cn";

/**
 * Renders one picker per option type (Size, Color, …) derived from the
 * variants, and reports the variant matching the full selection — or null
 * while the choice is incomplete or unmatched.
 */
export default function VariantSelector({
  variants,
  selected,
  onSelect,
}: {
  variants: ProductVariant[];
  selected: ProductVariant | null;
  onSelect: (v: ProductVariant | null) => void;
}) {
  // Option types in first-seen order, each with its distinct values.
  const optionTypes = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const v of variants) {
      for (const [k, val] of Object.entries(v.options)) {
        const vals = map.get(k) ?? [];
        if (!vals.includes(val)) vals.push(val);
        map.set(k, vals);
      }
    }
    return [...map.entries()].map(([name, values]) => ({ name, values }));
  }, [variants]);

  const [choice, setChoice] = useState<Record<string, string>>(selected?.options ?? {});

  const resolve = (next: Record<string, string>): ProductVariant | null => {
    if (optionTypes.some((t) => !next[t.name])) return null;
    return (
      variants.find((v) =>
        optionTypes.every((t) => v.options[t.name] === next[t.name]),
      ) ?? null
    );
  };

  const pick = (name: string, value: string) => {
    const next = { ...choice, [name]: value };
    setChoice(next);
    onSelect(resolve(next));
  };

  // Is a given value still selectable given the *other* current choices, and
  // does the resulting variant have stock? Used to grey out dead ends.
  const valueState = (name: string, value: string) => {
    const hypothetical = { ...choice, [name]: value };
    const match = variants.find((v) =>
      Object.entries(hypothetical).every(([k, val]) => v.options[k] === val),
    );
    return { exists: !!match, inStock: !!match && match.in_stock };
  };

  return (
    <div className="mt-4 space-y-4">
      {optionTypes.map((type) => (
        <div key={type.name}>
          <div className="text-sm text-zinc-600 mb-1.5">
            {type.name}
            {choice[type.name] && (
              <span className="font-medium text-ink"> · {choice[type.name]}</span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {type.values.map((value) => {
              const active = choice[type.name] === value;
              const { exists, inStock } = valueState(type.name, value);
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => pick(type.name, value)}
                  disabled={!exists}
                  aria-pressed={active}
                  className={cn(
                    "min-w-[3rem] rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "border-brand bg-brand-light text-brand"
                      : "border-zinc-300 text-zinc-700 hover:border-zinc-400",
                    !exists && "cursor-not-allowed opacity-40",
                    exists && !inStock && !active && "text-zinc-400 line-through",
                  )}
                >
                  {value}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      {optionTypes.some((t) => !choice[t.name]) && (
        <p className="text-xs text-zinc-500">Select {optionTypes.map((t) => t.name).join(" & ")} to continue.</p>
      )}
      {selected && !selected.in_stock && (
        <p className="text-xs font-medium text-danger">This option is out of stock.</p>
      )}
    </div>
  );
}
