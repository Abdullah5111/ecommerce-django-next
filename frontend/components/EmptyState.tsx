import Link from "next/link";
import { buttonClasses } from "@/components/ui/Button";

export default function EmptyState({
  icon,
  title,
  message,
  ctaHref,
  ctaLabel,
}: {
  icon: React.ReactNode;
  title: string;
  message?: string;
  ctaHref?: string;
  ctaLabel?: string;
}) {
  return (
    <div className="text-center py-16">
      <div className="mx-auto mb-4 w-16 h-16 rounded-full bg-brand-light text-brand flex items-center justify-center">
        {icon}
      </div>
      <h2 className="text-xl font-semibold">{title}</h2>
      {message && <p className="text-zinc-500 mt-2 max-w-sm mx-auto">{message}</p>}
      {ctaHref && ctaLabel && (
        <Link href={ctaHref} className={buttonClasses("primary", "md", "mt-6")}>
          {ctaLabel}
        </Link>
      )}
    </div>
  );
}
