"use client";

import { useEffect, useState } from "react";

const pad = (n: number) => String(n).padStart(2, "0");

/** Counts down to the next local midnight. Client-only to avoid an SSR/CSR hydration mismatch. */
export default function CountdownTimer() {
  const [parts, setParts] = useState<string[] | null>(null);

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const end = new Date(now);
      end.setHours(24, 0, 0, 0);
      let s = Math.max(0, Math.floor((end.getTime() - now.getTime()) / 1000));
      const h = Math.floor(s / 3600);
      s %= 3600;
      setParts([pad(h), pad(Math.floor(s / 60)), pad(s % 60)]);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  if (!parts) return null;

  return (
    <span className="inline-flex items-center gap-1" aria-label={`Ends in ${parts.join(":")}`}>
      {parts.map((p, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          {i > 0 && <span className="font-bold text-deal-dark">:</span>}
          <span className="rounded bg-ink text-white text-xs font-bold px-1.5 py-1 tabular-nums">{p}</span>
        </span>
      ))}
    </span>
  );
}
