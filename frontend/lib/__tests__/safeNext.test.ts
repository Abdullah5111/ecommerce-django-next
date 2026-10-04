import { describe, expect, it } from "vitest";
import { safeNext } from "../safeNext";

describe("safeNext", () => {
  it("keeps same-site paths, including query strings", () => {
    expect(safeNext("/checkout")).toBe("/checkout");
    expect(safeNext("/orders/12?placed=1")).toBe("/orders/12?placed=1");
  });

  it("falls back when there is no target", () => {
    expect(safeNext(null)).toBe("/");
    expect(safeNext("")).toBe("/");
    expect(safeNext(undefined, "/account")).toBe("/account");
  });

  it("rejects off-site targets", () => {
    for (const raw of [
      "https://evil.example",
      "//evil.example",
      "/\\evil.example", // browsers normalise "\" to "/" → protocol-relative
      "javascript:alert(1)",
      "evil.example",
    ]) {
      expect(safeNext(raw), raw).toBe("/");
    }
  });
});
