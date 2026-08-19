"use client";

// Catches errors thrown by the root layout itself, so it must render its own
// <html>/<body> (it replaces the layout). Kept dependency-free and self-contained.
import "./globals.css";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex flex-col items-center justify-center text-center px-4">
          <h1 className="text-2xl font-semibold">Something went wrong</h1>
          <p className="text-zinc-500 mt-2 max-w-sm">
            A critical error occurred while loading the app. Please try again.
          </p>
          <button
            onClick={reset}
            className="mt-6 h-11 px-5 rounded-lg bg-brand text-brand-fg text-sm font-medium hover:bg-brand-dark"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
