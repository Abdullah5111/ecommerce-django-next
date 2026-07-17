"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { useToast } from "@/lib/useToast";

export default function HelpfulButton({
  reviewId,
  initialCount,
  initialVoted,
  isOwnReview = false,
}: {
  reviewId: number;
  initialCount: number;
  initialVoted: boolean;
  isOwnReview?: boolean;
}) {
  const router = useRouter();
  const { toast } = useToast();
  const [count, setCount] = useState(initialCount);
  const [voted, setVoted] = useState(initialVoted);
  const [pending, setPending] = useState(false);

  // You can't vote on your own review — show the tally without the control.
  if (isOwnReview) {
    return (
      <span className="text-xs text-zinc-500">
        {count > 0 ? `${count} found this helpful` : "No votes yet"}
      </span>
    );
  }

  const onClick = async () => {
    const token = auth.get();
    if (!token) {
      router.push(
        "/login?next=" + encodeURIComponent(window.location.pathname)
      );
      return;
    }

    const next = !voted;
    // Optimistic: flip immediately, roll back if the request fails.
    setVoted(next);
    setCount((c) => c + (next ? 1 : -1));
    setPending(true);
    try {
      const res = await api.voteHelpful(token, reviewId, next);
      setCount(res.helpful_count);
      setVoted(res.helpful_by_me);
    } catch {
      setVoted(!next);
      setCount((c) => c + (next ? -1 : 1));
      toast("Could not save your vote. Please try again.", "error");
    } finally {
      setPending(false);
    }
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      aria-pressed={voted}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        voted
          ? "border-brand bg-brand-light text-brand"
          : "border-zinc-300 text-zinc-600 hover:border-zinc-400 hover:bg-zinc-50",
        pending && "opacity-60",
      )}
    >
      <svg width="14" height="14" viewBox="0 0 20 20" aria-hidden="true" fill="currentColor">
        <path d="M7.5 18h7.2a2 2 0 0 0 1.95-1.56l1.3-5.5A1.6 1.6 0 0 0 16.4 9H12V4.5A2.5 2.5 0 0 0 9.5 2c-.5 0-.9.3-1.06.77L6.4 9H7.5v9zM2 9.5A1.5 1.5 0 0 1 3.5 8h1v10h-1A1.5 1.5 0 0 1 2 16.5v-7z" />
      </svg>
      Helpful{count > 0 ? ` (${count})` : ""}
    </button>
  );
}
