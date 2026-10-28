// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Cart, Product, ProductVariant } from "../api";

const mocks = vi.hoisted(() => ({
  user: null as { id: number } | null,
  token: null as string | null,
  api: {
    addToCart: vi.fn(),
    getCart: vi.fn(),
    mergeCart: vi.fn(),
    removeCartItem: vi.fn(),
    updateCartItem: vi.fn(),
    clearCart: vi.fn(),
  },
}));

vi.mock("../useAuth", () => ({ useAuth: () => ({ user: mocks.user }) }));
vi.mock("../auth", () => ({ auth: { get: () => mocks.token } }));
vi.mock("../api", () => ({ api: mocks.api }));

import { CartProvider, useCart } from "../cart";

function product(id: number, price: string): Product {
  return { id, name: `P${id}`, price } as Product;
}

function variant(id: number, price: string): ProductVariant {
  return { id, effective_price: price } as ProductVariant;
}

function renderCart() {
  return renderHook(() => useCart(), {
    wrapper: ({ children }) => <CartProvider>{children}</CartProvider>,
  });
}

beforeEach(() => {
  mocks.user = null;
  mocks.token = null;
  Object.values(mocks.api).forEach((fn) => fn.mockReset());
  window.localStorage.clear();
});

afterEach(cleanup);

describe("guest cart", () => {
  it("merges repeat adds into one line and keeps variants separate", async () => {
    const { result } = renderCart();
    const shirt = product(1, "10.00");
    act(() => result.current.add(shirt));
    act(() => result.current.add(shirt, null, 2));
    act(() => result.current.add(shirt, variant(7, "12.00")));
    expect(result.current.items).toHaveLength(2);
    expect(result.current.items[0].quantity).toBe(3);
    // 3 × 10.00 + 1 × the variant's own price.
    expect(result.current.total).toBeCloseTo(42);
  });

  it("persists to localStorage and restores on the next visit", async () => {
    const first = renderCart();
    act(() => first.result.current.add(product(1, "5.00"), null, 2));
    await waitFor(() =>
      expect(JSON.parse(window.localStorage.getItem("shop_cart") ?? "[]")).toHaveLength(1)
    );
    first.unmount();

    const second = renderCart();
    await waitFor(() => expect(second.result.current.items).toHaveLength(1));
    expect(second.result.current.total).toBeCloseTo(10);
  });

  it("drops a line when its quantity is set to zero", () => {
    const { result } = renderCart();
    act(() => result.current.add(product(1, "5.00")));
    act(() => result.current.update(1, null, 0));
    expect(result.current.items).toHaveLength(0);
  });

  it("never calls the server", () => {
    const { result } = renderCart();
    act(() => result.current.add(product(1, "5.00")));
    expect(mocks.api.addToCart).not.toHaveBeenCalled();
  });
});

describe("signed-in cart", () => {
  const serverCart = (quantity: number): Cart =>
    ({ items: [{ product: product(1, "5.00"), variant: null, quantity }] }) as Cart;

  it("merges the guest cart into the server on sign-in, then clears it locally", async () => {
    window.localStorage.setItem(
      "shop_cart",
      JSON.stringify([{ product: product(1, "5.00"), variant: null, quantity: 2 }])
    );
    mocks.user = { id: 9 };
    mocks.token = "tok";
    mocks.api.mergeCart.mockResolvedValue(serverCart(2));
    mocks.api.getCart.mockResolvedValue(serverCart(2));

    const { result } = renderCart();
    await waitFor(() => expect(result.current.items).toHaveLength(1));
    expect(mocks.api.mergeCart).toHaveBeenCalledWith("tok", {
      items: [{ product: 1, variant: null, quantity: 2 }],
    });
    expect(window.localStorage.getItem("shop_cart")).toBeNull();
  });

  it("adds optimistically, then takes the server's answer (e.g. a stock cap)", async () => {
    mocks.user = { id: 9 };
    mocks.token = "tok";
    mocks.api.getCart.mockResolvedValue({ items: [] } as unknown as Cart);
    mocks.api.addToCart.mockResolvedValue(serverCart(3));

    const { result } = renderCart();
    await waitFor(() => expect(mocks.api.getCart).toHaveBeenCalled());
    act(() => result.current.add(product(1, "5.00"), null, 10));
    expect(result.current.items[0].quantity).toBe(10); // optimistic
    await waitFor(() => expect(result.current.items[0].quantity).toBe(3)); // server-capped
  });
});
