import Link from "next/link";

type Cat = { id: number; name: string; full_slug: string };

const ICONS: Record<string, string> = {
  electronics: "🎧",
  computers: "💻",
  fashion: "👕",
  apparel: "👕",
  shoes: "👟",
  beauty: "💄",
  home: "🛋️",
  "home & kitchen": "🍳",
  kitchen: "🍳",
  sports: "🏀",
  outdoors: "🏕️",
  toys: "🧸",
  books: "📚",
  gaming: "🎮",
  grocery: "🛒",
  pets: "🐾",
  jewelry: "💎",
  watches: "⌚",
  phones: "📱",
  audio: "🎤",
};

const TINTS = [
  "from-indigo-50",
  "from-amber-50",
  "from-emerald-50",
  "from-rose-50",
  "from-sky-50",
  "from-violet-50",
];

export default function CategoryTiles({ categories }: { categories: Cat[] }) {
  if (categories.length === 0) return null;
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold mb-3">Shop by category</h2>
      <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        {categories.map((c, i) => (
          <Link
            key={c.id}
            href={`/c/${c.full_slug}`}
            className={`group rounded-card border border-zinc-200 bg-gradient-to-b ${TINTS[i % TINTS.length]} to-white p-4 flex items-center justify-center text-center hover:shadow-card-hover hover:-translate-y-0.5 transition-all`}
          >
            <span className="text-center">
              <span className="block text-2xl mb-1" aria-hidden>
                {ICONS[c.name.toLowerCase()] ?? "🛍️"}
              </span>
              <span className="text-sm font-medium group-hover:text-brand">{c.name}</span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
