import { describe, expect, it } from "vitest";

import { cardExpiry, cardLabel, isExpired } from "../cards";

describe("saved card formatting", () => {
  it("labels known and unknown brands", () => {
    expect(cardLabel({ brand: "visa", last4: "4242" })).toBe("Visa •••• 4242");
    expect(cardLabel({ brand: "amex", last4: "0005" })).toBe("American Express •••• 0005");
    expect(cardLabel({ brand: "newco", last4: "1111" })).toBe("Newco •••• 1111");
  });

  it("formats expiry as MM/YY", () => {
    expect(cardExpiry({ exp_month: 4, exp_year: 2027 })).toBe("04/27");
  });

  it("treats a card as valid through its expiry month", () => {
    const oct2026 = new Date(2026, 9, 15);
    expect(isExpired({ exp_month: 10, exp_year: 2026 }, oct2026)).toBe(false);
    expect(isExpired({ exp_month: 9, exp_year: 2026 }, oct2026)).toBe(true);
    expect(isExpired({ exp_month: 1, exp_year: 2027 }, oct2026)).toBe(false);
    expect(isExpired({ exp_month: 12, exp_year: 2025 }, oct2026)).toBe(true);
  });
});
