/** A fresh Idempotency-Key for one checkout attempt (at most 64 chars). */
export function newIdempotencyKey(): string {
  // randomUUID needs a secure context (https or localhost); fall back otherwise.
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
