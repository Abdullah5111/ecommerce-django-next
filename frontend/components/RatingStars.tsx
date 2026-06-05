type Props = {
  value: string | number;
  count: number;
  size?: "sm" | "md";
};

function Star({ fill, size }: { fill: "full" | "half" | "empty"; size: number }) {
  if (fill === "half") {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 20 20"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="half-grad">
            <stop offset="50%" stopColor="#facc15" />
            <stop offset="50%" stopColor="#e4e4e7" />
          </linearGradient>
        </defs>
        <path
          d="M10 1.5l2.6 5.3 5.9.86-4.25 4.14 1 5.85L10 14.9 4.75 17.65l1-5.85L1.5 7.66l5.9-.86L10 1.5z"
          fill="url(#half-grad)"
        />
      </svg>
    );
  }
  const color = fill === "full" ? "#facc15" : "#e4e4e7";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M10 1.5l2.6 5.3 5.9.86-4.25 4.14 1 5.85L10 14.9 4.75 17.65l1-5.85L1.5 7.66l5.9-.86L10 1.5z"
        fill={color}
      />
    </svg>
  );
}

export default function RatingStars({ value, count, size = "sm" }: Props) {
  if (count === 0) return null;

  const numeric = typeof value === "string" ? parseFloat(value) : value;
  const safeValue = isNaN(numeric) ? 0 : numeric;
  const rounded = Math.round(safeValue * 2) / 2;
  const px = size === "sm" ? 14 : 18;
  const textCls = size === "sm" ? "text-xs" : "text-sm";

  const stars: ("full" | "half" | "empty")[] = [];
  for (let i = 1; i <= 5; i++) {
    if (rounded >= i) stars.push("full");
    else if (rounded >= i - 0.5) stars.push("half");
    else stars.push("empty");
  }

  return (
    <div className={`inline-flex items-center gap-1 ${textCls} text-zinc-600`}>
      <div className="inline-flex">
        {stars.map((s, i) => (
          <Star key={i} fill={s} size={px} />
        ))}
      </div>
      <span>
        {safeValue.toFixed(1)} ({count})
      </span>
    </div>
  );
}
