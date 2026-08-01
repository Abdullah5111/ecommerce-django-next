"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";

/**
 * Resolves the per-viewer bits of a review list. Server-rendered reviews are always
 * unauthenticated (JWT is in localStorage), so helpful_by_me/is_mine come back false;
 * this re-requests the list once with the token and shares the answer with every
 * HelpfulButton (one request between them, not one each).
 */
type ViewerState = {
  votedIds: Set<number>;
  mineIds: Set<number>;
  /** True until the viewer's state is known. */
  pending: boolean;
};

// Start pending on both server and client so hydration matches (token is in
// localStorage, invisible during SSR); otherwise the viewer's own review flashes
// an enabled Helpful button before the lookup corrects it.
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
        // Leave buttons usable on failure; a stale vote self-corrects on the next click.
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
