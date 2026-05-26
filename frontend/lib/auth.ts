"use client";

const KEY = "shop_token";

export const auth = {
  get: () => (typeof window === "undefined" ? null : window.localStorage.getItem(KEY)),
  set: (token: string) => window.localStorage.setItem(KEY, token),
  clear: () => window.localStorage.removeItem(KEY),
};
