// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("session restore", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("removes tokens a previous version left in localStorage", async () => {
    window.localStorage.setItem("shop_token", "old-access");
    window.localStorage.setItem("shop_refresh", "old-refresh");
    await import("../auth");
    expect(window.localStorage.getItem("shop_token")).toBeNull();
    expect(window.localStorage.getItem("shop_refresh")).toBeNull();
  });

  it("trades the cookie for an access token, once for concurrent callers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access: "fresh" }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { restoreSession } = await import("../api");
    const { auth } = await import("../auth");

    const [a, b] = await Promise.all([restoreSession(), restoreSession()]);
    expect(a).toBe("fresh");
    expect(b).toBe("fresh");
    expect(fetchMock).toHaveBeenCalledTimes(1); // the refresh token rotates; never race it
    expect(auth.get()).toBe("fresh");

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/auth\/token\/refresh\/$/);
    expect(init.credentials).toBe("include");
    expect(init.headers["X-Requested-With"]).toBe("fetch");
    expect(init.body).toBeUndefined(); // the token is in the cookie, not script
  });

  it("resolves null when there is no session", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));
    const { restoreSession } = await import("../api");
    const { auth } = await import("../auth");
    expect(await restoreSession()).toBeNull();
    expect(auth.get()).toBeNull();
  });
});
