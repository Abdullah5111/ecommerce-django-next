const TONES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  paid: "bg-blue-100 text-blue-800",
  shipped: "bg-indigo-100 text-indigo-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-zinc-200 text-zinc-600",
  partially_refunded: "bg-orange-100 text-orange-800",
  refunded: "bg-rose-100 text-rose-800",
};

/** The one order-status chip — same colors and label on every surface
 * (customer list/detail, staff console, dashboard). */
export default function OrderStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize whitespace-nowrap ${
        TONES[status] ?? "bg-zinc-100 text-zinc-600"
      }`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
