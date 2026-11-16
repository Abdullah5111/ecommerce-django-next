import { describe, expect, it } from "vitest";

import { fieldErrors } from "../apiErrors";

describe("fieldErrors", () => {
  it("maps DRF field lists to messages", () => {
    const err = new Error('API 400: {"new_password": ["Too short.", "Too common."]}');
    expect(fieldErrors(err)).toEqual({ new_password: "Too short. Too common." });
  });

  it("keeps a detail string", () => {
    expect(fieldErrors(new Error('API 429: {"detail": "Slow down."}'))).toEqual({
      detail: "Slow down.",
    });
  });

  it("falls back to a generic message for non-JSON failures", () => {
    expect(fieldErrors(new Error("Failed to fetch")).detail).toMatch(/try again/);
  });
});
