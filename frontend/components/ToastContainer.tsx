"use client";

import { useToast } from "@/lib/useToast";

export default function ToastContainer() {
  const { toasts } = useToast();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => {
        const accent =
          t.variant === "success"
            ? "border-l-4 border-l-green-500"
            : t.variant === "error"
              ? "border-l-4 border-l-red-500"
              : "border-l-4 border-l-zinc-400";
        return (
          <div
            key={t.id}
            className={`pointer-events-auto bg-white border ${accent} rounded-md shadow-md px-4 py-2.5 text-sm text-zinc-800 min-w-[200px] animate-[slideIn_0.2s_ease-out]`}
            style={{
              animation: "toastSlideIn 0.2s ease-out",
            }}
          >
            {t.message}
          </div>
        );
      })}
      <style jsx>{`
        @keyframes toastSlideIn {
          from {
            transform: translateX(20px);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
