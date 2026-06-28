/** Compact "units sold" label, e.g. 1 → "1", 1500 → "1.5k", 12000 → "12k". */
export function formatSold(n: number): string {
  if (n < 1000) return String(n);
  const k = n / 1000;
  return `${k % 1 === 0 ? k.toFixed(0) : k.toFixed(1)}k`;
}
