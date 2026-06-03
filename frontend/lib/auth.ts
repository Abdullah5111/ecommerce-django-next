"use client";

const ACCESS_KEY = "shop_token";
const REFRESH_KEY = "shop_refresh";

export const auth = {
  get: () => (typeof window === "undefined" ? null : window.localStorage.getItem(ACCESS_KEY)),
  getRefresh: () =>
    typeof window === "undefined" ? null : window.localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh?: string) => {
    window.localStorage.setItem(ACCESS_KEY, access);
    if (refresh) window.localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};
