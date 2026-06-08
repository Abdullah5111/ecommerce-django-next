"use client";

import Link from "next/link";
import { useAuth } from "@/lib/useAuth";
import WriteReviewForm from "./WriteReviewForm";

export default function ReviewCta({ slug }: { slug: string }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="text-sm text-zinc-500">Loading…</div>;
  }
  if (!user) {
    return (
      <div className="border rounded-lg p-4 bg-zinc-50 text-sm">
        <Link href="/login" className="underline font-medium">
          Sign in
        </Link>{" "}
        to write a review.
      </div>
    );
  }
  return <WriteReviewForm slug={slug} />;
}
