"use client";

import { api, type AppNotification, type ChatMessage } from "./api";
import { auth } from "./auth";

export type RealtimeMessage =
  | { type: "notification"; notification: AppNotification; unread_count: number }
  | { type: "unread_count"; unread: number }
  // chat — see backend/chat/consumers.py for the server side
  | { type: "chat.message"; message: ChatMessage }
  | { type: "chat.typing"; user_id: number; thread_user_id: number }
  | { type: "chat.read"; thread_user_id: number; reader_id: number; read_at: string }
  | { type: "chat.presence"; user_id: number; online: boolean }
  // emitted on every (re)connect so subscribers can catch up on missed events
  | { type: "realtime.open" };

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
      emit({ type: "realtime.open" });
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
  // Ephemeral client→server frames (typing, read receipts, thread watch).
  // Dropped while disconnected — reconnect's resync re-derives state anyway.
  send(obj: Record<string, unknown>) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  },
};
