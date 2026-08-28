"use client";

import { api, type AppNotification } from "./api";
import { auth } from "./auth";

export type RealtimeMessage =
  | { type: "notification"; notification: AppNotification; unread_count: number }
  | { type: "unread_count"; unread: number };

type Listener = (msg: RealtimeMessage) => void;

// Module-level singleton: one WebSocket per tab, shared by every subscriber
// (NotificationBell, order pages). Server-push only — mutations stay on REST.
let ws: WebSocket | null = null;
let retry = 0;
let timer: ReturnType<typeof setTimeout> | undefined;
let closed = false;
const listeners = new Set<Listener>();

function url(): string | null {
  const token = auth.get(); // null during SSR / when logged out
  if (!token) return null;
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api")
    .replace(/\/api\/?$/, "")
    .replace(/^http/, "ws");
  return `${base}/ws/notifications/?token=${encodeURIComponent(token)}`;
}

function emit(msg: RealtimeMessage) {
  listeners.forEach((fn) => fn(msg));
}

// Catch-up after (re)connect: the socket may have missed pushes, so re-fetch
// the unread count as server truth. Goes through request()'s refresh-on-401,
// which also rotates the token the next reconnect dials with.
function resync() {
  const token = auth.get();
  if (!token) return;
  api
    .unreadNotificationCount(token)
    .then(({ unread }) => emit({ type: "unread_count", unread }))
    .catch(() => {});
}

export const realtime = {
  connect() {
    const u = url();
    if (!u) return;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    closed = false;
    ws = new WebSocket(u);
    ws.onmessage = (e) => {
      try {
        emit(JSON.parse(e.data) as RealtimeMessage);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onopen = () => {
      retry = 0;
      resync();
    };
    ws.onclose = () => {
      if (closed) return;
      timer = setTimeout(realtime.connect, Math.min(1000 * 2 ** retry++, 30_000));
    };
  },
  disconnect() {
    closed = true;
    if (timer) clearTimeout(timer);
    ws?.close();
    ws = null;
    retry = 0;
  },
  subscribe(fn: Listener) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};
