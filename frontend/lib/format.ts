/**
 * Localized "medium date, short time" — e.g. "Jul 29, 2026, 3:04 PM".
 * Accepts null (renders ""), so order timelines can pass optional timestamps.
 */
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
