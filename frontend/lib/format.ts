/** Localized "medium date, short time" — e.g. "Jul 29, 2026, 3:04 PM". Null renders "". */
export function formatDateTime(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "";
}

/** Compact "units sold" label, e.g. 1 → "1", 1500 → "1.5k", 12000 → "12k". */
export function formatSold(n: number): string {
  if (n < 1000) return String(n);
  const k = n / 1000;
  return `${k % 1 === 0 ? k.toFixed(0) : k.toFixed(1)}k`;
}

/** "$12.34" — every rendered amount goes through this; backend decimals can
 * arrive unrounded. `freeText` renders when the amount is zero (shipping). */
export function formatMoney(value: string | number, freeText?: string): string {
  const n = Number(value);
  if (freeText && n === 0) return freeText;
  return `$${n.toFixed(2)}`;
}
