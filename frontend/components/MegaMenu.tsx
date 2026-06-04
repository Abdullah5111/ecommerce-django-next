"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, type CategoryTreeNode } from "@/lib/api";

export default function MegaMenu() {
  const [open, setOpen] = useState(false);
  const [tree, setTree] = useState<CategoryTreeNode[] | null>(null);
  const [error, setError] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getCategoryTree()
      .then((data) => {
        if (!cancelled) setTree(data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const clearCloseTimer = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const scheduleClose = () => {
    clearCloseTimer();
    closeTimer.current = setTimeout(() => setOpen(false), 150);
  };

  const handleLinkClick = () => {
    clearCloseTimer();
    setOpen(false);
  };

  return (
    <div
      ref={containerRef}
      className="relative"
      onMouseEnter={() => {
        clearCloseTimer();
        setOpen(true);
      }}
      onMouseLeave={scheduleClose}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        className="hover:underline"
      >
        Shop
      </button>

      {open && (
        <div
          className="hidden md:block absolute left-0 top-full mt-2 z-50 w-screen max-w-5xl bg-white border rounded shadow-lg p-6"
          onMouseEnter={clearCloseTimer}
          onMouseLeave={scheduleClose}
        >
          {error ? (
            <p className="text-sm text-zinc-500">Unable to load categories.</p>
          ) : !tree ? (
            <p className="text-sm text-zinc-500">Loading…</p>
          ) : tree.length === 0 ? (
            <p className="text-sm text-zinc-500">No categories.</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {tree.map((root) => (
                <div key={root.id}>
                  <Link
                    href={`/c/${root.full_slug}`}
                    onClick={handleLinkClick}
                    className="block font-semibold text-zinc-900 mb-2 hover:underline"
                  >
                    {root.name}
                  </Link>
                  <ul className="space-y-1">
                    {root.children.map((child) => (
                      <li key={child.id}>
                        <Link
                          href={`/c/${child.full_slug}`}
                          onClick={handleLinkClick}
                          className="text-sm text-zinc-600 hover:text-zinc-900 hover:underline"
                        >
                          {child.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
