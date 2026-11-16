// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ resendVerification: vi.fn() }));

vi.mock("@/lib/api", () => ({ api: mocks }));
vi.mock("@/lib/auth", () => ({ auth: { get: () => "access-jwt" } }));

import ResendVerificationButton from "../ResendVerificationButton";

// Braces matter: a function returned from beforeEach runs as teardown, and
// mockReset() returns the mock itself.
beforeEach(() => {
  mocks.resendVerification.mockReset();
});
afterEach(cleanup);

describe("ResendVerificationButton", () => {
  it("sends and shows the server's confirmation", async () => {
    mocks.resendVerification.mockResolvedValue({ detail: "We've sent a new link to a@b.co." });
    render(<ResendVerificationButton />);
    fireEvent.click(screen.getByRole("button", { name: "Resend link" }));
    expect((await screen.findByRole("status")).textContent).toBe(
      "We've sent a new link to a@b.co."
    );
    expect(mocks.resendVerification).toHaveBeenCalledWith("access-jwt");
  });

  it("shows the rate-limit message instead of failing silently", async () => {
    mocks.resendVerification.mockImplementation(async () => {
      throw new Error('API 429: {"detail": "Request was throttled. Expected available in 3600 seconds."}');
    });
    render(<ResendVerificationButton />);
    fireEvent.click(screen.getByRole("button", { name: "Resend link" }));
    expect((await screen.findByRole("status")).textContent).toMatch(/throttled/);
  });
});
