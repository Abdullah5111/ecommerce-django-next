"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";

export type GalleryImage = { url: string; alt: string };

export default function Gallery({ images }: { images: GalleryImage[] }) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const active = images[activeIdx] || images[0];

  const next = useCallback(() => {
    if (images.length === 0) return;
    setActiveIdx((i) => (i + 1) % images.length);
  }, [images.length]);

  const prev = useCallback(() => {
    if (images.length === 0) return;
    setActiveIdx((i) => (i - 1 + images.length) % images.length);
  }, [images.length]);

  useEffect(() => {
    if (!lightboxOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxOpen(false);
      else if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightboxOpen, next, prev]);

  if (images.length === 0) {
    return (
      <div className="relative aspect-square bg-zinc-100 rounded-lg" aria-label="No image" />
    );
  }

  return (
    <div className="flex flex-col md:flex-row gap-3">
      {images.length > 1 && (
        <div className="order-2 md:order-1 flex md:flex-col gap-2 md:w-16 shrink-0 overflow-x-auto md:overflow-x-visible">
          {images.map((img, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setActiveIdx(i)}
              className={`relative aspect-square w-16 md:w-auto shrink-0 rounded-md overflow-hidden border-2 bg-zinc-100 ${
                i === activeIdx ? "border-black" : "border-transparent hover:border-zinc-300"
              }`}
              aria-label={`View image ${i + 1}`}
            >
              <Image src={img.url} alt={img.alt} fill sizes="64px" className="object-cover" />
            </button>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={() => setLightboxOpen(true)}
        className="order-1 md:order-2 relative flex-1 aspect-square bg-zinc-100 rounded-lg overflow-hidden cursor-zoom-in"
        aria-label="Open image fullscreen"
      >
        {active && (
          <Image
            src={active.url}
            alt={active.alt}
            fill
            sizes="(min-width: 768px) 50vw, 100vw"
            priority
            className="object-cover"
          />
        )}
      </button>

      {lightboxOpen && active && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
          role="dialog"
          aria-modal="true"
          aria-label="Image viewer"
          onClick={() => setLightboxOpen(false)}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setLightboxOpen(false);
            }}
            className="absolute top-4 right-4 text-white text-2xl w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center"
            aria-label="Close"
          >
            x
          </button>
          {images.length > 1 && (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  prev();
                }}
                className="absolute left-4 top-1/2 -translate-y-1/2 text-white text-3xl w-12 h-12 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center"
                aria-label="Previous image"
              >
                {"<"}
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  next();
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-white text-3xl w-12 h-12 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center"
                aria-label="Next image"
              >
                {">"}
              </button>
            </>
          )}
          <div
            className="relative w-[90vw] h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            <Image
              src={active.url}
              alt={active.alt}
              fill
              sizes="90vw"
              className="object-contain"
            />
          </div>
        </div>
      )}
    </div>
  );
}
