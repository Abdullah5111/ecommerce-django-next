export default function ComingSoon({
  icon,
  title,
  blurb,
}: {
  icon: string;
  title: string;
  blurb: string;
}) {
  return (
    <div className="text-center py-16">
      <div className="text-5xl mb-4" aria-hidden>
        {icon}
      </div>
      <h1 className="text-2xl font-bold mb-2">{title}</h1>
      <p className="text-zinc-500 max-w-sm mx-auto">{blurb}</p>
      <span className="inline-block mt-6 text-xs px-3 py-1 rounded-full bg-zinc-100 text-zinc-600 border border-zinc-200">
        Coming soon
      </span>
    </div>
  );
}
