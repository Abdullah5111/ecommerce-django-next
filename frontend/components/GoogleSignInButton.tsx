"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";

const GIS_SRC = "https://accounts.google.com/gsi/client";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (resp: { credential: string }) => void;
          }) => void;
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

function loadGis(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("Failed to load Google")));
      return;
    }
    const script = document.createElement("script");
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google"));
    document.head.appendChild(script);
  });
}

/**
 * Google Identity Services sign-in. Renders nothing unless the backend reports
 * Google sign-in is configured (so the keyless demo just shows nothing). On a
 * successful credential it exchanges the Google ID token for our JWT pair.
 */
export default function GoogleSignInButton({ next = "/" }: { next?: string }) {
  const { refresh } = useAuth();
  const router = useRouter();
  const ref = useRef<HTMLDivElement>(null);
  const [available, setAvailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getGoogleConfig()
      .then(async (cfg) => {
        if (!cfg.enabled || !cfg.client_id) return;
        await loadGis();
        if (cancelled || !ref.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: cfg.client_id,
          callback: async (resp) => {
            try {
              const { access, refresh: refreshToken } = await api.googleLogin(resp.credential);
              auth.set(access, refreshToken);
              await refresh();
              router.push(next);
            } catch {
              setError("Google sign-in failed");
            }
          },
        });
        window.google.accounts.id.renderButton(ref.current, {
          theme: "outline",
          size: "large",
          width: 320,
          text: "continue_with",
        });
        setAvailable(true);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [next, refresh, router]);

  return (
    <div className={available ? "mt-4" : ""}>
      {available && (
        <div className="flex items-center gap-3 my-4 text-xs text-zinc-400">
          <span className="flex-1 h-px bg-zinc-200" />
          OR
          <span className="flex-1 h-px bg-zinc-200" />
        </div>
      )}
      <div ref={ref} className="flex justify-center" />
      {error && <p className="text-red-600 mt-2 text-sm">{error}</p>}
    </div>
  );
}
