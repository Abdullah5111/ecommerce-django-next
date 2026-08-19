"use client";

import { useEffect } from "react";
import Link from "next/link";
import Button, { buttonClasses } from "@/components/ui/Button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface it; wire an error reporter (e.g. Sentry) here in production.
    console.error(error);
  }, [error]);

  return (
    <div className="text-center py-20">
      <div className="mx-auto mb-4 w-16 h-16 rounded-full bg-brand-light text-brand flex items-center justify-center text-3xl font-bold">
        !
      </div>
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="text-zinc-500 mt-2 max-w-sm mx-auto">
        An unexpected error occurred. You can try again, or head back to the shop.
      </p>
      <div className="flex gap-3 justify-center mt-6">
        <Button onClick={reset}>Try again</Button>
        <Link href="/" className={buttonClasses("secondary", "md")}>
          Back to shop
        </Link>
      </div>
    </div>
  );
}
