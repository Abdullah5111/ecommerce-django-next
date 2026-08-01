"use client";

import { useEffect, useState } from "react";
import type { ReviewImage } from "@/lib/api";

export default function ReviewPhotos({ images }: { images: ReviewImage[] }) {
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    if (open === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(null);
      if (e.key === "ArrowRight") setOpen((i) => (i === null ? i : (i + 1) % images.length));
      if (e.key === "ArrowLeft")
        setOpen((i) => (i === null ? i : (i - 1 + images.length) % images.length));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, images.length]);

  return (
    <>
      <ul className="mt-3 flex flex-wrap gap-2">
        {images.map((img, i) => (
          <li key={img.id}>
            <button
              type="button"
              onClick={() => setOpen(i)}
              className="block h-16 w-16 overflow-hidden rounded border hover:opacity-90"
              aria-label={`Open reviewer photo ${i + 1}`}
            >
              {/* Plain <img>: API host isn't in next.config remotePatterns, so next/image rejects it. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img.image}
                alt={`Reviewer photo ${i + 1}`}
                className="h-full w-full object-cover"
                loading="lazy"
              />
            </button>
          </li>
        ))}
      </ul>

      {open !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setOpen(null)}
          role="dialog"
          aria-modal="true"
          aria-label="Reviewer photo"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={images[open].image}
            alt={`Reviewer photo ${open + 1}`}
            className="max-h-full max-w-full object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            type="button"
            onClick={() => setOpen(null)}
            className="absolute right-4 top-4 text-3xl leading-none text-white"
            aria-label="Close"
          >
            ×
          </button>
        </div>
      )}
    </>
  );
}
