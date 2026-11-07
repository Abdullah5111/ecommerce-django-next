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
// Presence heartbeat: the server treats a connection unseen for 90s as gone
// (backend/chat/presence.py), so an open socket pings every 30s.
const HEARTBEAT_MS = 30_000;
let heartbeat: ReturnType<typeof setInterval> | undefined;

function stopHeartbeat() {
  if (heartbeat) clearInterval(heartbeat);
  heartbeat = undefined;
}
let closed = false;
// True while a ticket request is in flight, so concurrent connect() calls
// don't each fetch one and open a socket.
let connecting = false;
const listeners = new Set<Listener>();

function url(ticket: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api")
    .replace(/\/api\/?$/, "")
    .replace(/^http/, "ws");
  // /ws/chat/ carries both chat and notification pushes (one socket per tab);
  // /ws/notifications/ only pushes, and would drop every chat frame we send.
  // A one-time ticket, not the access token: URLs end up in access logs.
  return `${base}/ws/chat/?ticket=${encodeURIComponent(ticket)}`;
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

function scheduleReconnect() {
  timer = setTimeout(realtime.connect, Math.min(1000 * 2 ** retry++, 30_000));
}

function open(u: string) {
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
    stopHeartbeat();
    heartbeat = setInterval(() => realtime.send({ type: "chat.ping" }), HEARTBEAT_MS);
    emit({ type: "realtime.open" });
    resync();
  };
  ws.onclose = () => {
    stopHeartbeat();
    if (closed) return;
    scheduleReconnect(); // with a fresh ticket: each one works once
  };
}

export const realtime = {
  connect() {
    const token = auth.get(); // null during SSR / when logged out
    if (!token || connecting) return;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    closed = false;
    connecting = true;
    api
      .createWsTicket(token)
      .then(({ ticket }) => {
        connecting = false;
        if (!closed) open(url(ticket)); // disconnect() may have run meanwhile
      })
      .catch(() => {
        connecting = false;
        if (!closed) scheduleReconnect();
      });
  },
  disconnect() {
    closed = true;
    stopHeartbeat();
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
