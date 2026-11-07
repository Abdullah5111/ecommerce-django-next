// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ createWsTicket: vi.fn(), unreadNotificationCount: vi.fn() }));

vi.mock("../auth", () => ({ auth: { get: () => "access-jwt" } }));
vi.mock("../api", () => ({ api: mocks }));

import { realtime } from "../realtime";

class FakeSocket {
  static instances: FakeSocket[] = [];
  static OPEN = 1;
  static CONNECTING = 0;
  readyState = FakeSocket.CONNECTING;
  sent: string[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {}
}

// Let the ticket request's .then run.
const settle = async () => {
  for (let i = 0; i < 3; i++) await Promise.resolve();
};

beforeEach(() => {
  let n = 0;
  mocks.createWsTicket.mockReset().mockImplementation(async () => ({ ticket: `t${++n}`, expires_in: 30 }));
  mocks.unreadNotificationCount.mockReset().mockResolvedValue({ unread: 0 });
  vi.stubGlobal("WebSocket", FakeSocket);
});

afterEach(() => {
  realtime.disconnect();
  FakeSocket.instances = [];
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("realtime socket", () => {
  it("dials /ws/chat/ with a one-time ticket, never the access token", async () => {
    realtime.connect();
    await settle();
    expect(mocks.createWsTicket).toHaveBeenCalledWith("access-jwt");
    expect(FakeSocket.instances).toHaveLength(1);
    const { url } = FakeSocket.instances[0];
    // /ws/notifications/ drops every client frame — chat would be dead there.
    expect(url).toMatch(/\/ws\/chat\/\?ticket=t1$/);
    expect(url).not.toContain("access-jwt");
  });

  it("asks for one ticket even if connect() is called twice", async () => {
    realtime.connect();
    realtime.connect();
    await settle();
    expect(mocks.createWsTicket).toHaveBeenCalledTimes(1);
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("fetches a fresh ticket for every reconnect (each works once)", async () => {
    vi.useFakeTimers();
    realtime.connect();
    await settle();
    const first = FakeSocket.instances[0];
    first.readyState = 3; // CLOSED: browsers fire onclose only once closed
    first.onclose?.();
    vi.advanceTimersByTime(1000);
    await settle();
    expect(FakeSocket.instances).toHaveLength(2);
    expect(FakeSocket.instances[1].url).toMatch(/ticket=t2$/);
  });

  it("retries with backoff when the ticket request fails", async () => {
    vi.useFakeTimers();
    mocks.createWsTicket.mockRejectedValueOnce(new Error("API 503"));
    realtime.connect();
    await settle();
    expect(FakeSocket.instances).toHaveLength(0);
    vi.advanceTimersByTime(1000);
    await settle();
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("opens nothing if disconnected while the ticket was in flight", async () => {
    realtime.connect();
    realtime.disconnect();
    await settle();
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("pings every 30s while open, and stops when closed", async () => {
    vi.useFakeTimers();
    realtime.connect();
    await settle();
    const socket = FakeSocket.instances[0];
    socket.readyState = FakeSocket.OPEN;
    socket.onopen?.();
    vi.advanceTimersByTime(90_000);
    const pings = () => socket.sent.filter((f) => JSON.parse(f).type === "chat.ping").length;
    expect(pings()).toBe(3);

    realtime.disconnect();
    vi.advanceTimersByTime(90_000);
    expect(pings()).toBe(3);
  });

  it("sends chat frames on that same socket", async () => {
    realtime.connect();
    await settle();
    const socket = FakeSocket.instances[0];
    socket.readyState = FakeSocket.OPEN;
    realtime.send({ type: "chat.typing" });
    expect(socket.sent).toEqual([JSON.stringify({ type: "chat.typing" })]);
  });
});
