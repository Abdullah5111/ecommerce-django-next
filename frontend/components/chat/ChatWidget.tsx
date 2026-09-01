"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ChatMessage, type ChatThread } from "@/lib/api";
import { auth } from "@/lib/auth";
import { realtime } from "@/lib/realtime";
import { useAuth } from "@/lib/useAuth";
import MessageList from "./MessageList";

/** Buyer-side floating support chat (staff use /staff/chat instead). */
export default function ChatWidget() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState<ChatThread | null>(null);
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [olderCursor, setOlderCursor] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [unread, setUnread] = useState(0);
  const [typing, setTyping] = useState(false);
  const [staffOnline, setStaffOnline] = useState(false);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const lastTypingSent = useRef(0);

  const loadThread = useCallback(async () => {
    const token = auth.get();
    if (!token) return;
    try {
      const t = await api.getChatThread(token);
      setThread(t);
      setUnread(t.unread);
    } catch {
      /* widget stays closed-state; retry on next open */
    }
  }, []);

  const markRead = useCallback(() => {
    setUnread(0);
    setThread((t) => (t ? { ...t, unread: 0 } : t));
    realtime.send({ type: "chat.read" });
  }, []);

  const loadMessages = useCallback(async () => {
    const token = auth.get();
    if (!token) return;
    try {
      const page = await api.listChatMessages(token);
      // The API returns newest-first; render chronologically (oldest at top).
      setMessages([...page.results].reverse());
      setOlderCursor(page.next ? new URL(page.next).searchParams.get("cursor") : null);
    } catch {
      setMessages([]);
    }
  }, []);

  const loadOlder = async () => {
    const token = auth.get();
    if (!token || !olderCursor) return;
    const page = await api.listChatMessages(token, { cursor: olderCursor });
    setMessages((prev) => (prev ? [...[...page.results].reverse(), ...prev] : prev));
    setOlderCursor(page.next ? new URL(page.next).searchParams.get("cursor") : null);
  };

  useEffect(() => {
    if (!user || user.is_staff) return;
    realtime.connect();
    loadThread();
    return () => clearTimeout(typingTimer.current);
  }, [user, loadThread]);

  useEffect(() => {
    if (!user || user.is_staff) return;
    const meId = user.id;
    return realtime.subscribe((msg) => {
      if (msg.type === "chat.message") {
        const m = msg.message;
        setMessages((prev) =>
          prev && !prev.some((x) => x.id === m.id) ? [...prev, m] : prev,
        );
        setThread((t) =>
          t && m.thread_user_id === t.user
            ? { ...t, last_message_at: m.created_at, last_message_body: m.body }
            : t,
        );
        if (m.sender !== meId) {
          setTyping(false);
          // open panel: receipt goes out immediately; closed: badge it
          if (open) markRead();
          else setUnread((u) => u + 1);
        }
      } else if (msg.type === "chat.read") {
        // the other side read my messages — flip the ticks
        setMessages((prev) =>
          prev
            ? prev.map((m) =>
                m.sender === meId && !m.read_at ? { ...m, read_at: msg.read_at } : m,
              )
            : prev,
        );
      } else if (msg.type === "chat.typing" && msg.user_id !== meId) {
        setTyping(true);
        clearTimeout(typingTimer.current);
        typingTimer.current = setTimeout(() => setTyping(false), 3000);
      } else if (msg.type === "chat.presence" && msg.user_id !== meId) {
        setStaffOnline(msg.online);
      } else if (msg.type === "realtime.open") {
        loadThread();
        if (open) loadMessages().then(markRead);
      }
    });
  }, [user, open, loadThread, loadMessages, markRead]);

  useEffect(() => {
    if (open) {
      loadMessages().then(markRead);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const send = async () => {
    const body = input.trim();
    const token = auth.get();
    if (!body || !token) return;
    setInput("");
    try {
      const m = await api.sendChatMessage(token, body);
      setMessages((prev) => (prev && !prev.some((x) => x.id === m.id) ? [...prev, m] : prev));
      setThread((t) =>
        t ? { ...t, last_message_at: m.created_at, last_message_body: m.body } : t,
      );
    } catch {
      setInput(body); // restore for retry
    }
  };

  const onInput = (value: string) => {
    setInput(value);
    const now = Date.now();
    if (now - lastTypingSent.current > 2500) {
      lastTypingSent.current = now;
      realtime.send({ type: "chat.typing" });
    }
  };

  if (!user || user.is_staff) return null;

  return (
    <div className="fixed bottom-20 right-4 z-40 flex flex-col items-end gap-2 md:bottom-4">
      {open && (
        <div className="w-[calc(100vw-2rem)] max-w-sm bg-white border rounded-xl shadow-pop overflow-hidden flex flex-col h-[28rem]">
          <div className="px-4 py-2.5 border-b flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Support</p>
              <p className="text-[11px] text-zinc-500 flex items-center gap-1">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${staffOnline ? "bg-green-500" : "bg-zinc-300"}`}
                  aria-hidden
                />
                {staffOnline ? "Online now" : "We typically reply within a day"}
              </p>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close chat" className="text-zinc-400 hover:text-zinc-600">
              ✕
            </button>
          </div>

          {messages === null ? (
            <p className="text-zinc-500 text-sm text-center py-10">Loading…</p>
          ) : (
            <>
              {olderCursor && (
                <button onClick={loadOlder} className="text-xs text-brand hover:underline pt-2 self-center">
                  Load older messages
                </button>
              )}
              <MessageList messages={messages} meId={user.id} typing={typing} className="flex-1" />
            </>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="border-t p-2 flex gap-2"
          >
            <input
              value={input}
              onChange={(e) => onInput(e.target.value)}
              placeholder="Type a message…"
              maxLength={2000}
              className="flex-1 border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand"
              aria-label="Message"
            />
            <button
              type="submit"
              disabled={!input.trim()}
              className="bg-brand text-brand-fg rounded px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </div>
      )}

      <button
        onClick={() => setOpen(!open)}
        aria-label={open ? "Close support chat" : `Open support chat${unread ? ` (${unread} unread)` : ""}`}
        className="relative h-12 w-12 rounded-full bg-brand text-brand-fg shadow-pop flex items-center justify-center hover:bg-brand-dark"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        {!open && unread > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-600 text-white rounded-full min-w-5 h-5 px-1 text-xs flex items-center justify-center">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
    </div>
  );
}
