"use client";

// The access token lives only in this module's memory; the refresh token is an
// httpOnly cookie the API sets (backend/accounts/cookies.py), which script —
// including anything injected by an XSS bug — can't read. A page load starts
// with no access token and restores it from the cookie (`restoreSession`).
let accessToken: string | null = null;

// Tokens used to live in localStorage; drop any a previous version left there.
const LEGACY_KEYS = ["shop_token", "shop_refresh"];
if (typeof window !== "undefined") {
  try {
    LEGACY_KEYS.forEach((k) => window.localStorage.removeItem(k));
  } catch {
    // storage blocked — nothing to clean up
  }
}

export const auth = {
  get: () => accessToken,
  set: (access: string) => {
    accessToken = access;
  },
  clear: () => {
    accessToken = null;
  },
};
