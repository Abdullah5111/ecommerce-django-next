"use client";

import { buttonClasses } from "@/components/ui/Button";

/** Server pages can't retry a failed fetch themselves — this is the one
 * "backend down" surface, with a working reload button (unlike error.tsx,
 * which only covers client-side exceptions). */
export default function BackendUnreachable() {
  return (
    <div className="text-center py-20">
      <h2 className="text-2xl font-semibold">Backend unreachable</h2>
      <p className="text-zinc-500 mt-2">Start the Django API and retry. See README for setup.</p>
      <button onClick={() => window.location.reload()} className={buttonClasses("primary", "md", "mt-6")}>
        Retry
      </button>
    </div>
  );
}
