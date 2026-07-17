"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";

/**
 * Resolves the per-viewer bits of a review list.
 *
 * The product page server-renders its reviews, and the JWT lives in
 * localStorage — so that fetch is always unauthenticated and the server can
 * only ever report helpful_by_me/is_mine as false. This re-requests the same
 * list once from the client with the token attached and shares the answer with
 * every HelpfulButton, so the buttons cost one request between them rather
 * than one each.
 *
 * `helpful_count` is not viewer-specific, so the server-rendered value is
 * already correct and is not re-read here.
 */
type ViewerState = {
  votedIds: Set<number>;
  mineIds: Set<number>;
  /** True until the viewer's state is known. */
  pending: boolean;
};

// Start pending on both server and client so hydration matches (the token is in
// localStorage, invisible during SSR). Same shape as useAuth's `loading` gate.
// Without this, a logged-in user's own review would render an enabled Helpful
// button for a frame before the lookup corrects it.
const PENDING: ViewerState = {
  votedIds: new Set(),
  mineIds: new Set(),
  pending: true,
};

const SETTLED_EMPTY: ViewerState = {
  votedIds: new Set(),
  mineIds: new Set(),
  pending: false,
};

const ReviewViewerContext = createContext<ViewerState>(SETTLED_EMPTY);

export function useReviewViewer() {
  return useContext(ReviewViewerContext);
}

export default function ReviewViewerState({
  slug,
  children,
}: {
  slug: string;
  children: React.ReactNode;
}) {
  const [state, setState] = useState<ViewerState>(PENDING);

  useEffect(() => {
    const token = auth.get();
    if (!token) {
      // Guests have nothing to look up — settle immediately.
      setState(SETTLED_EMPTY);
      return;
    }

    let cancelled = false;
    setState(PENDING);

    api
      .listReviews(slug, undefined, undefined, token)
      .then((res) => {
        if (cancelled) return;
        setState({
          votedIds: new Set(
            res.results.filter((r) => r.helpful_by_me).map((r) => r.id)
          ),
          mineIds: new Set(res.results.filter((r) => r.is_mine).map((r) => r.id)),
          pending: false,
        });
      })
      .catch(() => {
        // Leave the buttons usable on failure; a stale vote just self-corrects
        // on the next click, which returns authoritative state.
        if (!cancelled) setState(SETTLED_EMPTY);
      });

    return () => {
      cancelled = true;
    };
  }, [slug]);

  return (
    <ReviewViewerContext.Provider value={state}>
      {children}
    </ReviewViewerContext.Provider>
  );
}
