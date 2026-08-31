"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/api";

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

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, typing]);

  return (
    <div className={`overflow-y-auto px-3 py-2 ${className}`}>
      {messages.length === 0 && !typing && (
        <p className="text-zinc-500 text-sm text-center py-8">
          No messages yet — say hello!
        </p>
      )}
      <ul className="space-y-2">
        {messages.map((m) => {
          const mine = m.sender === meId;
          return (
            <li key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  mine ? "bg-brand text-brand-fg" : "bg-zinc-100 text-zinc-900"
                }`}
              >
                <p className="whitespace-pre-wrap break-words">{m.body}</p>
                <div className={`flex items-center gap-1 mt-0.5 text-[10px] ${mine ? "text-brand-fg/70 justify-end" : "text-zinc-500"}`}>
                  <span>
                    {new Date(m.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  {mine && <span aria-label={m.read_at ? "Read" : "Sent"}>{m.read_at ? "✓✓" : "✓"}</span>}
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
