"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, type AppNotification } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";
import { realtime } from "@/lib/realtime";
import { useToast } from "@/lib/useToast";

export default function NotificationBell() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) {
      setUnread(0);
      realtime.disconnect();
      return;
    }
    let active = true;
    const token = auth.get();
    if (token) {
      api
        .unreadNotificationCount(token)
        .then(({ unread }) => {
          if (active) setUnread(unread);
        })
        .catch(() => {});
    }
    realtime.connect();
    const off = realtime.subscribe((msg) => {
      if (msg.type === "notification") {
        setUnread(msg.unread_count); // server truth, includes this one
        setItems((prev) => (prev ? [msg.notification, ...prev].slice(0, 8) : prev));
        toast(msg.notification.title, "success");
      } else if (msg.type === "unread_count") {
        setUnread(msg.unread);
      }
    });
    return () => {
      active = false;
      off();
    };
  }, [user, toast]);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next) {
      const token = auth.get();
      if (!token) return;
      try {
        const data = await api.listNotifications(token);
        setItems(data.results.slice(0, 8));
      } catch {
        setItems([]);
      }
    }
  };

  const markRead = async (n: AppNotification) => {
    if (n.is_read) return;
    const token = auth.get();
    if (!token) return;
    setItems((prev) => (prev ? prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)) : prev));
    setUnread((u) => Math.max(0, u - 1));
    try {
      await api.markNotificationRead(token, n.id);
    } catch {
      /* best-effort */
    }
  };

  if (!user) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={toggle}
        className="relative inline-flex items-center hover:text-zinc-900 text-zinc-600"
        aria-label={`Notifications${unread > 0 ? ` (${unread} unread)` : ""}`}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -top-2 -right-2 bg-red-600 text-white rounded-full px-1.5 text-[10px] leading-tight">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white border rounded-lg shadow-lg z-50 overflow-hidden">
          <div className="px-4 py-2 border-b flex items-center justify-between">
            <span className="font-medium text-sm">Notifications</span>
            <Link
              href="/account/notifications"
              onClick={() => setOpen(false)}
              className="text-xs text-blue-600 hover:underline"
            >
              See all
            </Link>
          </div>
          {items === null ? (
            <p className="px-4 py-6 text-sm text-zinc-500 text-center">Loading…</p>
          ) : items.length === 0 ? (
            <p className="px-4 py-6 text-sm text-zinc-500 text-center">No notifications yet.</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto">
              {items.map((n) => {
                const body = (
                  <div className={`px-4 py-3 border-b last:border-b-0 ${n.is_read ? "" : "bg-blue-50"}`}>
                    <div className="flex items-center gap-2">
                      {!n.is_read && <span className="h-2 w-2 rounded-full bg-blue-600 shrink-0" aria-hidden />}
                      <span className="text-sm font-medium">{n.title}</span>
                    </div>
                    {n.body && <p className="text-xs text-zinc-600 mt-0.5">{n.body}</p>}
                  </div>
                );
                return (
                  <li key={n.id}>
                    {n.order ? (
                      <Link href={`/orders/${n.order}`} onClick={() => { markRead(n); setOpen(false); }} className="block hover:bg-zinc-50">
                        {body}
                      </Link>
                    ) : (
                      <button onClick={() => markRead(n)} className="block w-full text-left hover:bg-zinc-50">
                        {body}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
