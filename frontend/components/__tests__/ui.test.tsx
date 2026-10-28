// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import FreeShippingBar from "../FreeShippingBar";
import OrderStatusBadge from "../ui/OrderStatusBadge";
import Price from "../ui/Price";

afterEach(cleanup);

describe("Price", () => {
  it("shows the price alone when not on sale", () => {
    const { container } = render(<Price price="19.5" />);
    expect(container.textContent).toBe("$19.50");
  });

  it("strikes through the compare-at price and shows the discount", () => {
    render(<Price price="75.00" compareAt="100.00" />);
    expect(screen.getByText("$75.00")).toBeTruthy();
    expect(screen.getByText("$100.00").className).toContain("line-through");
    expect(screen.getByText("−25%")).toBeTruthy();
  });

  it("ignores a compare-at that isn't higher than the price", () => {
    const { container } = render(<Price price="50" compareAt="40" />);
    expect(container.textContent).toBe("$50.00");
  });

  it("can hide the percentage", () => {
    render(<Price price="75" compareAt="100" showPercent={false} />);
    expect(screen.queryByText("−25%")).toBeNull();
  });
});

describe("FreeShippingBar", () => {
  it("says how much more is needed", () => {
    render(<FreeShippingBar subtotal={42.5} />);
    expect(screen.getByText("$7.50")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("42.5");
  });

  it("confirms free shipping at the threshold", () => {
    render(<FreeShippingBar subtotal={50} />);
    expect(screen.getByText(/unlocked free shipping/)).toBeTruthy();
  });

  it("caps the progress value above the threshold", () => {
    render(<FreeShippingBar subtotal={120} />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("50");
  });
});

describe("OrderStatusBadge", () => {
  it("humanises the status", () => {
    render(<OrderStatusBadge status="partially_refunded" />);
    expect(screen.getByText("partially refunded")).toBeTruthy();
  });

  it("falls back to a neutral tone for unknown statuses", () => {
    render(<OrderStatusBadge status="mystery" />);
    expect(screen.getByText("mystery").className).toContain("bg-zinc-100");
  });
});
