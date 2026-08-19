import Link from "next/link";
import { buttonClasses } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="text-center py-20">
      <p className="text-6xl font-bold text-brand">404</p>
      <h1 className="text-2xl font-semibold mt-4">Page not found</h1>
      <p className="text-zinc-500 mt-2 max-w-sm mx-auto">
        The page you&rsquo;re looking for doesn&rsquo;t exist or may have moved.
      </p>
      <Link href="/" className={buttonClasses("primary", "md", "mt-6")}>
        Back to shop
      </Link>
    </div>
  );
}
