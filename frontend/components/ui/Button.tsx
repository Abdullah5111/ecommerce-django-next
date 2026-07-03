import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "deal";
export type ButtonSize = "sm" | "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-colors " +
  "disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap";

const sizes: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-5 text-sm",
  lg: "h-12 px-6 text-base",
};

const variants: Record<ButtonVariant, string> = {
  primary: "bg-brand text-brand-fg hover:bg-brand-dark shadow-sm",
  secondary: "bg-white text-ink border border-zinc-300 hover:border-brand hover:text-brand",
  ghost: "bg-transparent text-ink hover:bg-zinc-100",
  deal: "bg-deal text-ink hover:bg-deal-dark hover:text-white shadow-sm",
};

/** Shared button/link styles — use for a `<Link>` that should look like a button. */
export function buttonClasses(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  className?: string,
): string {
  return cn(base, sizes[size], variants[variant], className);
}

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
};

const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = "primary", size = "md", fullWidth, className, ...props }, ref) => (
    <button
      ref={ref}
      className={buttonClasses(variant, size, cn(fullWidth && "w-full", className))}
      {...props}
    />
  ),
);
Button.displayName = "Button";

export default Button;
