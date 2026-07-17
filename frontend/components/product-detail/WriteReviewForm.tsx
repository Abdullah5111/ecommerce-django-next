"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useToast } from "@/lib/useToast";

// Mirrors MAX_REVIEW_IMAGES on the server, which rejects anything above this.
const MAX_PHOTOS = 5;

function StarInput({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="inline-flex gap-1" role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => {
        const filled = n <= value;
        return (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            onClick={() => onChange(n)}
            className="p-0.5"
            aria-label={`${n} star${n === 1 ? "" : "s"}`}
          >
            <svg width="28" height="28" viewBox="0 0 20 20" aria-hidden="true">
              <path
                d="M10 1.5l2.6 5.3 5.9.86-4.25 4.14 1 5.85L10 14.9 4.75 17.65l1-5.85L1.5 7.66l5.9-.86L10 1.5z"
                fill={filled ? "#facc15" : "#e4e4e7"}
              />
            </svg>
          </button>
        );
      })}
    </div>
  );
}

export default function WriteReviewForm({ slug }: { slug: string }) {
  const router = useRouter();
  const { toast } = useToast();
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Build preview URLs once per file set and revoke them on change/unmount —
  // creating them inline during render would leak an object URL every render.
  const previews = useMemo(() => photos.map((f) => URL.createObjectURL(f)), [photos]);
  useEffect(() => {
    return () => previews.forEach((url) => URL.revokeObjectURL(url));
  }, [previews]);

  const onPickPhotos = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    if (!picked.length) return;
    setError(null);
    const next = [...photos, ...picked].slice(0, MAX_PHOTOS);
    if (photos.length + picked.length > MAX_PHOTOS) {
      setError(`You can attach up to ${MAX_PHOTOS} photos.`);
    }
    setPhotos(next);
    // Reset so picking the same file again still fires onChange.
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removePhoto = (idx: number) =>
    setPhotos((p) => p.filter((_, i) => i !== idx));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const token = auth.get();
    if (!token) {
      setError("You must be signed in to write a review.");
      return;
    }
    if (rating < 1 || rating > 5) {
      setError("Pick a star rating between 1 and 5.");
      return;
    }
    setSubmitting(true);
    try {
      await api.postReview(token, slug, {
        rating,
        title: title.trim() || undefined,
        body: body.trim() || undefined,
        images: photos.length ? photos : undefined,
      });
      toast("Review posted", "success");
      setTitle("");
      setBody("");
      setRating(5);
      setPhotos([]);
      router.refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("400")) {
        setError("You have already reviewed this product.");
      } else if (msg.includes("401")) {
        setError("Your session has expired. Please sign in again.");
      } else {
        setError("Could not submit review. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="border rounded-lg p-4 bg-white">
      <h3 className="font-semibold mb-3">Write a review</h3>
      <div className="mb-3">
        <label className="block text-sm text-zinc-600 mb-1">Rating</label>
        <StarInput value={rating} onChange={setRating} />
      </div>
      <div className="mb-3">
        <label htmlFor="review-title" className="block text-sm text-zinc-600 mb-1">
          Title
        </label>
        <input
          id="review-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
          maxLength={200}
        />
      </div>
      <div className="mb-3">
        <label htmlFor="review-body" className="block text-sm text-zinc-600 mb-1">
          Your review
        </label>
        <textarea
          id="review-body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm min-h-[100px]"
        />
      </div>
      <div className="mb-3">
        <label className="block text-sm text-zinc-600 mb-1">
          Photos <span className="text-zinc-400">(optional, up to {MAX_PHOTOS})</span>
        </label>
        {photos.length > 0 && (
          <ul className="flex flex-wrap gap-2 mb-2">
            {photos.map((file, i) => (
              <li key={`${file.name}-${i}`} className="relative">
                {/* Local object URL preview — no next/image (not a remote host). */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previews[i]}
                  alt={`Selected photo ${i + 1}`}
                  className="h-16 w-16 rounded border object-cover"
                />
                <button
                  type="button"
                  onClick={() => removePhoto(i)}
                  className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-xs leading-none text-white"
                  aria-label={`Remove photo ${i + 1}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {photos.length < MAX_PHOTOS && (
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={onPickPhotos}
            className="block w-full text-sm text-zinc-600 file:mr-3 file:rounded file:border-0 file:bg-zinc-100 file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-zinc-200"
          />
        )}
      </div>
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="bg-black text-white px-4 py-2 rounded font-medium hover:bg-zinc-800 disabled:bg-zinc-400"
      >
        {submitting ? "Submitting…" : "Submit review"}
      </button>
    </form>
  );
}
