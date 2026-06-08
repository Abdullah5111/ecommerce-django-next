"use client";

import { useEffect, useState, type ReactNode } from "react";

type TabKey = "description" | "specifications" | "reviews";

type Props = {
  description: ReactNode;
  specifications?: ReactNode;
  reviews: ReactNode;
};

const TABS: { key: TabKey; label: string }[] = [
  { key: "description", label: "Description" },
  { key: "specifications", label: "Specifications" },
  { key: "reviews", label: "Reviews" },
];

function hashToTab(hash: string): TabKey {
  const clean = hash.replace(/^#/, "");
  if (clean === "specifications" || clean === "reviews" || clean === "description") {
    return clean;
  }
  return "description";
}

export default function Tabs({ description, specifications, reviews }: Props) {
  const tabs = TABS.filter((t) => t.key !== "specifications" || !!specifications);
  const [active, setActive] = useState<TabKey>("description");

  useEffect(() => {
    setActive(hashToTab(window.location.hash));
    const onHash = () => setActive(hashToTab(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const select = (key: TabKey) => {
    setActive(key);
    if (typeof window !== "undefined") {
      history.replaceState(null, "", `#${key}`);
    }
  };

  return (
    <div className="mt-10" id={active}>
      <div className="border-b flex gap-6 overflow-x-auto" role="tablist">
        {tabs.map((t) => {
          const isActive = active === t.key;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => select(t.key)}
              className={`py-3 text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition ${
                isActive
                  ? "border-black text-black"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      <div className="py-6">
        {active === "description" && <div>{description}</div>}
        {active === "specifications" && specifications && <div>{specifications}</div>}
        {active === "reviews" && <div>{reviews}</div>}
      </div>
    </div>
  );
}
