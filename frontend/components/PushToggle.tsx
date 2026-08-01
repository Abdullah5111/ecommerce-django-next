"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useToast } from "@/lib/useToast";
import { isSubscribed, pushSupported, subscribe, unsubscribe } from "@/lib/push";

/** Browser-push opt-in; renders nothing unless the server has push enabled and the browser supports it. */
export default function PushToggle() {
  const { toast } = useToast();
  const [available, setAvailable] = useState(false);
  const [publicKey, setPublicKey] = useState("");
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!pushSupported()) return;
    api
      .getPushConfig()
      .then(async (cfg) => {
        if (!cfg.enabled || !cfg.public_key) return;
        setPublicKey(cfg.public_key);
        setAvailable(true);
        setOn(await isSubscribed());
      })
      .catch(() => undefined);
  }, []);

  if (!available) return null;

  const handleToggle = async () => {
    const token = auth.get();
    if (!token) return;
    setBusy(true);
    try {
      if (on) {
        await unsubscribe(token);
        setOn(false);
        toast("Browser push disabled", "success");
      } else {
        await subscribe(token, publicKey);
        setOn(true);
        toast("Browser push enabled", "success");
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not update push", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={handleToggle}
      disabled={busy}
      className="text-sm border rounded px-3 py-1.5 hover:border-zinc-400 disabled:opacity-50"
    >
      {busy ? "…" : on ? "🔔 Push on" : "🔕 Enable browser push"}
    </button>
  );
}
