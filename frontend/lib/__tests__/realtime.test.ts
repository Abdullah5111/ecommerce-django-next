// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../auth", () => ({ auth: { get: () => "tok en" } }));

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

afterEach(() => {
  realtime.disconnect();
  FakeSocket.instances = [];
  vi.unstubAllGlobals();
});

describe("realtime socket", () => {
  it("dials /ws/chat/, the socket that carries both chat and notifications", () => {
    vi.stubGlobal("WebSocket", FakeSocket);
    realtime.connect();
    expect(FakeSocket.instances).toHaveLength(1);
    // /ws/notifications/ drops every client frame — chat would be dead there.
    expect(FakeSocket.instances[0].url).toMatch(/\/ws\/chat\/\?token=tok%20en$/);
  });

  it("pings every 30s while open, and stops when closed", () => {
    vi.useFakeTimers();
    try {
      vi.stubGlobal("WebSocket", FakeSocket);
      realtime.connect();
      const socket = FakeSocket.instances[0];
      socket.readyState = FakeSocket.OPEN;
      socket.onopen?.();
      vi.advanceTimersByTime(90_000);
      const pings = () => socket.sent.filter((f) => JSON.parse(f).type === "chat.ping").length;
      expect(pings()).toBe(3);

      realtime.disconnect();
      vi.advanceTimersByTime(90_000);
      expect(pings()).toBe(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it("sends chat frames on that same socket", () => {
    vi.stubGlobal("WebSocket", FakeSocket);
    realtime.connect();
    const socket = FakeSocket.instances[0];
    socket.readyState = FakeSocket.OPEN;
    realtime.send({ type: "chat.typing" });
    expect(socket.sent).toEqual([JSON.stringify({ type: "chat.typing" })]);
  });
});
