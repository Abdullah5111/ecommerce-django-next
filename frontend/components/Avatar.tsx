function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0][0]!.toUpperCase();
  return (parts[0][0]! + parts[parts.length - 1][0]!).toUpperCase();
}

export default function Avatar({
  src,
  name,
  size = 56,
}: {
  src: string | null;
  name: string;
  size?: number;
}) {
  const dimension = { width: size, height: size };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={src}
        alt={name}
        style={dimension}
        className="rounded-full object-cover bg-zinc-100 border border-zinc-200"
      />
    );
  }
  return (
    <span
      style={{ ...dimension, fontSize: size * 0.4 }}
      className="rounded-full bg-zinc-900 text-white flex items-center justify-center font-semibold select-none"
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}
