import { afterEach, describe, expect, it, vi } from "vitest";
import { formatMoney, formatSold, formatTimeAgo } from "../format";

describe("formatMoney", () => {
  it("always renders two decimals, even for unrounded backend values", () => {
    expect(formatMoney("89.9932")).toBe("$89.99");
    expect(formatMoney("5")).toBe("$5.00");
    expect(formatMoney(12.5)).toBe("$12.50");
  });

  it("uses the free label only for zero, and only when one is given", () => {
    expect(formatMoney("0.00", "Free")).toBe("Free");
    expect(formatMoney("0.00")).toBe("$0.00");
    expect(formatMoney("4.99", "Free")).toBe("$4.99");
  });
});

describe("formatTimeAgo", () => {
  afterEach(() => vi.useRealTimers());

  it("buckets into just now / minutes / hours / days", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-04T12:00:00Z"));
    expect(formatTimeAgo("2026-10-04T11:59:30Z")).toBe("just now");
    expect(formatTimeAgo("2026-10-04T11:55:00Z")).toBe("5m ago");
    expect(formatTimeAgo("2026-10-04T09:00:00Z")).toBe("3h ago");
    expect(formatTimeAgo("2026-10-01T12:00:00Z")).toBe("3d ago");
  });
});

describe("formatSold", () => {
  it("abbreviates thousands", () => {
    expect(formatSold(999)).toBe("999");
    expect(formatSold(1500)).toBe("1.5k");
    expect(formatSold(12000)).toBe("12k");
  });
});
