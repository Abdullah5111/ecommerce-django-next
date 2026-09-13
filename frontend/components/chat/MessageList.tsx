"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/api";

function dayLabel(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (same(d, today)) return "Today";
  if (same(d, yesterday)) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Scrollable transcript shared by the buyer widget and the staff inbox. */
export default function MessageList({
  messages,
  meId,
  typing = false,
  className = "",
}: {
  messages: ChatMessage[];
  meId: number;
  typing?: boolean;
  className?: string;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  // scroll on new messages, not on "load older" prepends
  const lastId = messages.length ? messages[messages.length - 1].id : 0;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" }); // nearest: never scroll the page
  }, [lastId, typing]);

  return (
    <div className={`overflow-y-auto px-3 py-2 ${className}`}>
      {messages.length === 0 && !typing && (
        <p className="text-zinc-500 text-sm text-center py-8">
          No messages yet — say hello!
        </p>
      )}
      <ul className="space-y-2" aria-live="polite">
        {messages.map((m, i) => {
          const mine = m.sender === meId;
          const prev = i > 0 ? messages[i - 1] : null;
          const newDay =
            !prev ||
            new Date(prev.created_at).toDateString() !== new Date(m.created_at).toDateString();
          return (
            <li key={m.id}>
              {newDay && (
                <div className="flex justify-center my-2">
                  <span className="text-[10px] uppercase tracking-wide text-zinc-400 bg-zinc-100 rounded-full px-2 py-0.5">
                    {dayLabel(m.created_at)}
                  </span>
                </div>
              )}
              <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                    mine ? "bg-brand text-brand-fg" : "bg-zinc-100 text-zinc-900"
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words">{m.body}</p>
                  <div
                    className={`flex items-center gap-1 mt-0.5 text-[10px] ${
                      mine ? "text-brand-fg/70 justify-end" : "text-zinc-500"
                    }`}
                  >
                    <span>
                      {new Date(m.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    {mine && (
                      <span aria-label={m.read_at ? "Read" : "Sent"}>
                        {m.read_at ? "✓✓" : "✓"}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </li>
          );
        })}
        {typing && (
          <li className="flex justify-start">
            <div className="bg-zinc-100 rounded-lg px-3 py-2 text-sm text-zinc-500 italic">
              typing…
            </div>
          </li>
        )}
      </ul>
      <div ref={endRef} />
    </div>
  );
}
