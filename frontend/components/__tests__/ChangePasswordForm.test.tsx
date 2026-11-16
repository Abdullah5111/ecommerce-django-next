// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  changePassword: vi.fn(),
  set: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: { changePassword: mocks.changePassword } }));
vi.mock("@/lib/auth", () => ({ auth: { get: () => "access-jwt", set: mocks.set } }));

import ChangePasswordForm from "../ChangePasswordForm";

function fill(current: string, next: string, confirm: string) {
  fireEvent.change(screen.getByPlaceholderText("Current password"), { target: { value: current } });
  fireEvent.change(screen.getByPlaceholderText("New password"), { target: { value: next } });
  fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
    target: { value: confirm },
  });
  fireEvent.submit(screen.getByRole("form", { name: "Change password" }));
}

beforeEach(() => {
  mocks.changePassword.mockReset();
  mocks.set.mockReset();
});

afterEach(cleanup);

describe("ChangePasswordForm", () => {
  it("catches a mismatched confirmation before calling the API", () => {
    render(<ChangePasswordForm onDone={vi.fn()} onCancel={vi.fn()} />);
    fill("old-pw", "new-pass-1", "new-pass-2");
    expect(screen.getByRole("alert").textContent).toMatch(/don't match/);
    expect(mocks.changePassword).not.toHaveBeenCalled();
  });

  it("stores the fresh access token and reports success", async () => {
    mocks.changePassword.mockResolvedValue({ access: "fresh-jwt" });
    const onDone = vi.fn();
    render(<ChangePasswordForm onDone={onDone} onCancel={vi.fn()} />);
    fill("old-pw", "new-pass-1", "new-pass-1");
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(mocks.changePassword).toHaveBeenCalledWith("access-jwt", "old-pw", "new-pass-1");
    expect(mocks.set).toHaveBeenCalledWith("fresh-jwt");
  });

  it("shows the server's message under the right field", async () => {
    mocks.changePassword.mockRejectedValue(
      new Error('API 400: {"current_password": ["Your current password is incorrect."]}')
    );
    const onDone = vi.fn();
    render(<ChangePasswordForm onDone={onDone} onCancel={vi.fn()} />);
    fill("wrong", "new-pass-1", "new-pass-1");
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Your current password is incorrect."
    );
    expect(onDone).not.toHaveBeenCalled();
    expect(mocks.set).not.toHaveBeenCalled();
  });
});
