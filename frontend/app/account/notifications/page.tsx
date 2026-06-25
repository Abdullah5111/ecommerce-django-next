"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type AppNotification, type NotificationKind } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";
import { useToast } from "@/lib/useToast";

const ICONS: Record<NotificationKind, string> = {
  order_paid: "✅",
  order_shipped: "📦",
  order_delivered: "🎉",
  order_cancelled: "✖️",
  order_refunded: "💸",
};

function timeAgo(iso: string): string {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function NotificationsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { toast } = useToast();

  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.push("/login?next=/account/notifications");
  }, [authLoading, user, router]);

  const load = useCallback(async () => {
    const token = auth.get();
    if (!token) return;
    try {
      const data = await api.listNotifications(token);
      setItems(data.results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load notifications");
      setItems([]);
    }
  }, []);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  const markRead = async (n: AppNotification) => {
    if (n.is_read) return;
    const token = auth.get();
    if (!token) return;
    setItems((prev) =>
      prev ? prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)) : prev,
    );
    try {
      await api.markNotificationRead(token, n.id);
    } catch {
      load(); // revert to server truth on failure
    }
  };

  const markAllRead = async () => {
    const token = auth.get();
    if (!token) return;
    setItems((prev) => (prev ? prev.map((x) => ({ ...x, is_read: true })) : prev));
    try {
      await api.markAllNotificationsRead(token);
      toast("All caught up", "success");
    } catch {
      load();
    }
  };

  if (authLoading || items === null) {
    return <p className="text-zinc-600">Loading…</p>;
  }

  const unread = items.filter((n) => !n.is_read).length;

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Notifications</h1>
        {unread > 0 && (
          <button onClick={markAllRead} className="text-sm text-blue-600 hover:underline">
            Mark all read
          </button>
        )}
      </div>

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {items.length === 0 ? (
        <p className="text-zinc-500 py-12 text-center">No notifications yet.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((n) => {
            const inner = (
              <div
                className={`flex gap-3 rounded border p-3 ${
                  n.is_read ? "bg-white border-zinc-200" : "bg-blue-50 border-blue-200"
                }`}
              >
                <span className="text-xl leading-none" aria-hidden>
                  {ICONS[n.kind] ?? "🔔"}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{n.title}</span>
                    {!n.is_read && (
                      <span className="h-2 w-2 rounded-full bg-blue-600" aria-label="unread" />
                    )}
                  </div>
                  {n.body && <p className="text-sm text-zinc-600">{n.body}</p>}
                  <p className="text-xs text-zinc-400 mt-1">{timeAgo(n.created_at)}</p>
                </div>
              </div>
            );
            return (
              <li key={n.id}>
                {n.order ? (
                  <Link href={`/orders/${n.order}`} onClick={() => markRead(n)} className="block">
                    {inner}
                  </Link>
                ) : (
                  <button onClick={() => markRead(n)} className="block w-full text-left">
                    {inner}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
