import { describe, expect, it } from "vitest";

import { newIdempotencyKey } from "../idempotency";

describe("newIdempotencyKey", () => {
  it("returns distinct keys within the server's 64-char limit", () => {
    const a = newIdempotencyKey();
    const b = newIdempotencyKey();
    expect(a).not.toBe(b);
    expect(a.length).toBeLessThanOrEqual(64);
  });

  it("falls back to getRandomValues where randomUUID is missing", () => {
    // Insecure contexts (plain http, not localhost) have no randomUUID.
    const original = crypto.randomUUID;
    Object.defineProperty(crypto, "randomUUID", { value: undefined, configurable: true });
    try {
      expect(newIdempotencyKey()).toMatch(/^[0-9a-f]{32}$/);
    } finally {
      Object.defineProperty(crypto, "randomUUID", { value: original, configurable: true });
    }
  });
});
