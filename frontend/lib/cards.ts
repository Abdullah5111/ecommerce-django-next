import type { SavedCard } from "./api";

const BRANDS: Record<string, string> = {
  amex: "American Express",
  diners: "Diners Club",
  discover: "Discover",
  jcb: "JCB",
  mastercard: "Mastercard",
  unionpay: "UnionPay",
  visa: "Visa",
};

/** "Visa •••• 4242" */
export function cardLabel(card: Pick<SavedCard, "brand" | "last4">): string {
  const brand = BRANDS[card.brand] ?? card.brand.charAt(0).toUpperCase() + card.brand.slice(1);
  return `${brand} •••• ${card.last4}`;
}

/** "04/27" */
export function cardExpiry(card: Pick<SavedCard, "exp_month" | "exp_year">): string {
  return `${String(card.exp_month).padStart(2, "0")}/${String(card.exp_year).slice(-2)}`;
}

/** A card is valid through the last day of its expiry month. */
export function isExpired(
  card: Pick<SavedCard, "exp_month" | "exp_year">,
  now: Date = new Date()
): boolean {
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  return card.exp_year < year || (card.exp_year === year && card.exp_month < month);
}
