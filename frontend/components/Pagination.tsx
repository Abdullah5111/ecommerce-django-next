import Link from "next/link";

type Props = {
  currentPage: number;
  totalPages: number;
  pathname: string;
  searchParams: Record<string, string | undefined>;
};

function buildHref(
  pathname: string,
  searchParams: Record<string, string | undefined>,
  page: number,
) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(searchParams)) {
    if (k === "page") continue;
    if (v !== undefined && v !== "") qs.set(k, v);
  }
  if (page > 1) qs.set("page", String(page));
  const s = qs.toString();
  return s ? `${pathname}?${s}` : pathname;
}

function pageNumbers(current: number, total: number): (number | "ellipsis")[] {
  const pages = new Set<number>();
  pages.add(1);
  pages.add(total);
  for (let i = current - 2; i <= current + 2; i++) {
    if (i >= 1 && i <= total) pages.add(i);
  }
  const sorted = Array.from(pages).sort((a, b) => a - b);
  const result: (number | "ellipsis")[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) result.push("ellipsis");
    result.push(sorted[i]);
  }
  return result;
}

export default function Pagination({ currentPage, totalPages, pathname, searchParams }: Props) {
  if (totalPages <= 1) return null;

  const pages = pageNumbers(currentPage, totalPages);
  const prevDisabled = currentPage <= 1;
  const nextDisabled = currentPage >= totalPages;

  const baseBtn = "px-3 py-1.5 text-sm rounded border min-w-[2.25rem] text-center";
  const inactive = "bg-white border-zinc-200 hover:border-zinc-400 text-zinc-700";
  const active = "bg-black text-white border-black";
  const disabled = "bg-zinc-50 text-zinc-300 border-zinc-100 pointer-events-none";

  return (
    <nav className="flex flex-wrap items-center justify-center gap-1 mt-8" aria-label="Pagination">
      <Link
        href={buildHref(pathname, searchParams, Math.max(1, currentPage - 1))}
        className={`${baseBtn} ${prevDisabled ? disabled : inactive}`}
        aria-disabled={prevDisabled}
      >
        « Prev
      </Link>
      {pages.map((p, i) =>
        p === "ellipsis" ? (
          <span key={`e-${i}`} className="px-2 text-zinc-400 text-sm">
            …
          </span>
        ) : (
          <Link
            key={p}
            href={buildHref(pathname, searchParams, p)}
            className={`${baseBtn} ${p === currentPage ? active : inactive}`}
            aria-current={p === currentPage ? "page" : undefined}
          >
            {p}
          </Link>
        ),
      )}
      <Link
        href={buildHref(pathname, searchParams, Math.min(totalPages, currentPage + 1))}
        className={`${baseBtn} ${nextDisabled ? disabled : inactive}`}
        aria-disabled={nextDisabled}
      >
        Next »
      </Link>
    </nav>
  );
}
