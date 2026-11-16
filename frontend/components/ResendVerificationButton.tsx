"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { fieldErrors } from "@/lib/apiErrors";
import { auth } from "@/lib/auth";

/** "Resend link" next to an unverified email. Replaces itself with the
 * server's answer (sent, or e.g. rate-limited). */
export default function ResendVerificationButton() {
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [message, setMessage] = useState("");

  const resend = async () => {
    const token = auth.get();
    if (!token) return;
    setState("sending");
    try {
      const { detail } = await api.resendVerification(token);
      setMessage(detail);
    } catch (err) {
      setMessage(fieldErrors(err).detail ?? "Couldn't send the link. Please try again.");
    }
    setState("done");
  };

  if (state === "done") {
    return (
      <span className="text-xs text-zinc-600" role="status">
        {message}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={resend}
      disabled={state === "sending"}
      className="text-xs underline text-zinc-600 disabled:opacity-50"
    >
      {state === "sending" ? "Sending…" : "Resend link"}
    </button>
  );
}
