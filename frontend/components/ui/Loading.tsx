/** The one loading paragraph — pass a label to name the subject
 * ("Loading addresses…"), otherwise plain "Loading…". */
export default function Loading({ label, className = "py-12" }: { label?: string; className?: string }) {
  return (
    <p className={`text-zinc-500 text-center ${className}`}>{label ? `${label}…` : "Loading…"}</p>
  );
}
