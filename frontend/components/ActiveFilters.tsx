import Link from "next/link";

type Props = {
  pathname: string;
  search?: string;
  ordering?: string;
  priceMin?: string;
  priceMax?: string;
  inStock?: string;
};

function buildHrefWithout(
  pathname: string,
  current: Record<string, string | undefined>,
  removeKeys: string[]
) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(current)) {
    if (!v) continue;
    if (removeKeys.includes(k)) continue;
    qs.set(k, v);
  }
  const s = qs.toString();
  return s ? `${pathname}?${s}` : pathname;
}

export default function ActiveFilters({
  pathname,
  search,
  ordering,
  priceMin,
  priceMax,
  inStock,
}: Props) {
  const current = { search, ordering, priceMin, priceMax, inStock };
  const chips: { label: string; removeKeys: string[]; key: string }[] = [];

  if (priceMin || priceMax) {
    const label =
      priceMin && priceMax
        ? `Price: $${priceMin}–$${priceMax}`
        : priceMin
          ? `Price: ≥ $${priceMin}`
          : `Price: ≤ $${priceMax}`;
    chips.push({ key: "price", label, removeKeys: ["priceMin", "priceMax"] });
  }
  if (inStock === "true") {
    chips.push({ key: "inStock", label: "In stock", removeKeys: ["inStock"] });
  }

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {chips.map((c) => (
        <Link
          key={c.key}
          href={buildHrefWithout(pathname, current, c.removeKeys)}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs border bg-white hover:border-zinc-400"
        >
          <span>{c.label}</span>
          <span aria-hidden className="text-zinc-400">✕</span>
        </Link>
      ))}
    </div>
  );
}
