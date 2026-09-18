"use client";

import Loading from "@/components/ui/Loading";

import { buttonClasses } from "@/components/ui/Button";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type ChatMessage, type ChatThread } from "@/lib/api";
import { auth } from "@/lib/auth";
import { formatTimeAgo } from "@/lib/format";
import { realtime } from "@/lib/realtime";
import { useAuth } from "@/lib/useAuth";
import { useToast } from "@/lib/useToast";
import MessageList from "@/components/chat/MessageList";

/** Staff inbox: every customer thread, live. Gated on is_staff. */
export default function StaffChatPage() {
  const { user, loading: authLoading } = useAuth();
  const { toast } = useToast();
  const router = useRouter();

  const [threads, setThreads] = useState<ChatThread[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null); // customer user id
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [olderCursor, setOlderCursor] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [typingFrom, setTypingFrom] = useState<number | null>(null);
  const [presence, setPresence] = useState<Record<number, boolean>>({});
  const typingTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const lastTypingSent = useRef(0);
  const threadsRef = useRef<ChatThread[] | null>(null);
  const selectedRef = useRef<number | null>(null);

  useEffect(() => {
    threadsRef.current = threads;
  }, [threads]);

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  useEffect(() => {
    if (!authLoading && (!user || !user.is_staff)) router.replace("/");
  }, [authLoading, user, router]);

  const loadThreads = useCallback(async () => {
    const token = auth.get();
    if (!token) return;
    try {
      setThreads(await api.listChatThreads(token));
    } catch {
      setThreads([]);
    }
  }, []);

  const loadMessages = useCallback(async (uid: number) => {
    const token = auth.get();
    if (!token) return;
    try {
      const page = await api.listChatMessages(token, { thread: uid });
      // Rapid thread switching: only the newest selection may paint.
      if (selectedRef.current !== uid || selected !== uid) return;
      // The API returns newest-first; render chronologically (oldest at top).
      setMessages([...page.results].reverse());
      setOlderCursor(page.next ? new URL(page.next).searchParams.get("cursor") : null);
    } catch {
      if (selectedRef.current === uid) setMessages([]);
    }
  }, [selected]);

  const loadOlder = async () => {
    const token = auth.get();
    const uid = selected;
    if (!token || uid === null || !olderCursor) return;
    try {
      const page = await api.listChatMessages(token, { thread: uid, cursor: olderCursor });
      if (selectedRef.current !== uid) return; // switched threads mid-fetch
      setMessages((prev) => (prev ? [...[...page.results].reverse(), ...prev] : prev));
      setOlderCursor(page.next ? new URL(page.next).searchParams.get("cursor") : null);
    } catch {
      toast("Couldn't load older messages", "error");
    }
  };

  const clearUnread = useCallback((uid: number) => {
    setThreads((prev) => prev?.map((t) => (t.user === uid ? { ...t, unread: 0 } : t)) ?? prev);
  }, []);

  const unwatch = useCallback((uid: number | null) => {
    if (uid !== null) realtime.send({ type: "chat.unwatch", thread_user_id: uid });
  }, []);

  const openThread = useCallback(
    (uid: number) => {
      // leaving a thread must unwatch it, or its presence dot stays lit and
      // the connection keeps the group membership forever
      if (selectedRef.current !== null && selectedRef.current !== uid) {
        unwatch(selectedRef.current);
      }
      selectedRef.current = uid;
      setSelected(uid);
      setMessages(null);
      realtime.send({ type: "chat.watch", thread_user_id: uid });
      loadMessages(uid);
      clearUnread(uid);
      realtime.send({ type: "chat.read", thread_user_id: uid });
    },
    [loadMessages, clearUnread, unwatch],
  );

  const closeThread = useCallback(() => {
    unwatch(selectedRef.current);
    selectedRef.current = null;
    setSelected(null);
  }, [unwatch]);

  useEffect(() => {
    if (!user?.is_staff) return;
    realtime.connect();
    loadThreads();
    return () => clearTimeout(typingTimer.current);
  }, [user, loadThreads]);

  useEffect(() => {
    if (!user?.is_staff) return;
    const off = realtime.subscribe((msg) => {
      if (msg.type === "chat.message") {
        const m = msg.message;
        // a first-ever message creates a thread we don't have listed yet
        if (!threadsRef.current?.some((t) => t.user === m.thread_user_id)) loadThreads();
        setThreads((prev) =>
          prev?.map((t) =>
            t.user === m.thread_user_id
              ? { ...t, last_message_at: m.created_at, last_message_body: m.body }
              : t,
          ) ?? prev,
        );
        if (m.thread_user_id === selected) {
          setMessages((prev) =>
            prev && !prev.some((x) => x.id === m.id) ? [...prev, m] : prev,
          );
          if (m.sender !== user.id) {
            setTypingFrom(null);
            realtime.send({ type: "chat.read", thread_user_id: m.thread_user_id });
          }
        } else if (m.sender === null || m.sender === m.thread_user_id) {
          // customer message (null sender = deleted user) in an unopened thread
          setThreads((prev) =>
            prev?.map((t) => (t.user === m.thread_user_id ? { ...t, unread: t.unread + 1 } : t)) ??
            prev,
          );
        }
      } else if (msg.type === "chat.read") {
        clearUnread(msg.thread_user_id);
      } else if (msg.type === "chat.typing") {
        setTypingFrom(msg.user_id);
        clearTimeout(typingTimer.current);
        typingTimer.current = setTimeout(() => setTypingFrom(null), 3000);
      } else if (msg.type === "chat.presence") {
        setPresence((prev) => ({ ...prev, [msg.user_id]: msg.online }));
      } else if (msg.type === "realtime.open") {
        loadThreads();
        if (selected !== null) openThread(selected);
      }
    });
    return () => {
      off();
      clearTimeout(typingTimer.current);
    };
  }, [user, selected, loadThreads, openThread, clearUnread]);

  const send = async () => {
    const body = input.trim();
    const token = auth.get();
    if (!body || !token || selected === null) return;
    setInput("");
    try {
      const m = await api.sendChatMessage(token, body, selected);
      setMessages((prev) => (prev && !prev.some((x) => x.id === m.id) ? [...prev, m] : prev));
      setThreads((prev) =>
        prev?.map((t) =>
          t.user === selected
            ? { ...t, last_message_at: m.created_at, last_message_body: m.body }
            : t,
        ) ?? prev,
      );
    } catch {
      setInput(body); // restore for retry
      toast("Reply couldn't be sent — try again", "error");
    }
  };

  const onInput = (value: string) => {
    setInput(value);
    if (selected === null) return;
    const now = Date.now();
    if (now - lastTypingSent.current > 2500) {
      lastTypingSent.current = now;
      realtime.send({ type: "chat.typing", thread_user_id: selected });
    }
  };

  if (authLoading || !user?.is_staff) {
    return <Loading className="py-10 text-sm" />;
  }

  const selectedThread = threads?.find((t) => t.user === selected) ?? null;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Support inbox</h1>
      <div className="grid gap-4 md:grid-cols-[280px_1fr]">
        {/* Thread list */}
        <aside className={`${selected !== null ? "hidden md:block" : ""} border rounded-xl divide-y max-h-[70vh] overflow-y-auto`}>
          {threads === null ? (
            <Loading className="py-10 text-sm" />
          ) : threads.length === 0 ? (
            <p className="text-zinc-500 text-sm p-4">No customer conversations yet — they'll appear when someone messages.</p>
          ) : (
            threads.map((t) => (
              <button
                key={t.id}
                onClick={() => openThread(t.user)}
                className={`w-full text-left px-4 py-3 hover:bg-zinc-50 ${
                  t.user === selected
                    ? "bg-brand-light"
                    : t.unread > 0
                      ? "bg-brand-light/50"
                      : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-sm flex items-center gap-1.5 ${t.unread > 0 ? "font-semibold" : "font-medium"}`}>
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${presence[t.user] ? "bg-success" : "bg-zinc-300"}`}
                      aria-hidden
                    />
                    {t.username}
                  </span>
                  {t.unread > 0 && (
                    <span className="bg-red-600 text-white rounded-full px-1.5 text-[10px] leading-tight">
                      {t.unread}
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-500 truncate mt-0.5">
                  {t.last_message_body ?? "No messages yet"}
                </p>
                {t.last_message_at && (
                  <p className="text-[10px] text-zinc-400">{t.last_message_at ? formatTimeAgo(t.last_message_at) : ""}</p>
                )}
              </button>
            ))
          )}
        </aside>

        {/* Conversation pane */}
        <section className={`${selected === null ? "hidden md:flex" : "flex"} flex-col border rounded-xl h-[70vh]`}>
          {selected === null ? (
            <p className="m-auto text-zinc-500 text-sm">Select a conversation</p>
          ) : (
            <>
              <div className="px-4 py-2.5 border-b flex items-center justify-between">
                <p className="text-sm font-medium flex items-center gap-1.5">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${presence[selected] ? "bg-success" : "bg-zinc-300"}`}
                    aria-hidden
                  />
                  {selectedThread?.username ?? `Customer #${selected}`}
                </p>
                <button onClick={closeThread} className="text-xs text-zinc-500 hover:underline md:hidden">
                  Back
                </button>
                <button onClick={closeThread} aria-label="Close conversation" className="hidden md:inline text-zinc-400 hover:text-zinc-600 ml-3">
                  ✕
                </button>
              </div>
              {messages === null ? (
                <Loading className="py-10 text-sm" />
              ) : (
                <>
                  {olderCursor && (
                    <button onClick={loadOlder} className="text-xs text-brand hover:underline pt-2 self-center">
                      Load older messages
                    </button>
                  )}
                  <MessageList messages={messages} meId={user.id} typing={typingFrom === selected} className="flex-1" />
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
                  placeholder="Reply…"
                  maxLength={2000}
                  className="flex-1 border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand"
                  aria-label="Reply"
                />
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className={buttonClasses("primary", "sm")}
                >
                  Send
                </button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
