import Link from "next/link";

type Ancestor = { name: string; full_slug: string };

export default function Breadcrumbs({
  ancestors,
  current,
}: {
  ancestors: Ancestor[];
  current: string;
}) {
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-zinc-500 mb-4">
      <ol className="flex flex-wrap items-center gap-1">
        <li>
          <Link href="/" className="hover:text-zinc-900 hover:underline">
            Home
          </Link>
        </li>
        {ancestors.map((a) => (
          <li key={a.full_slug} className="flex items-center gap-1">
            <span className="text-zinc-400">/</span>
            <Link
              href={`/c/${a.full_slug}`}
              className="hover:text-zinc-900 hover:underline"
            >
              {a.name}
            </Link>
          </li>
        ))}
        <li className="flex items-center gap-1">
          <span className="text-zinc-400">/</span>
          <span className="text-zinc-900">{current}</span>
        </li>
      </ol>
    </nav>
  );
}
