/**
 * Field messages from a failed request. `request()` throws `API <status>: <body>`;
 * DRF bodies are `{"field": ["msg", ...]}` or `{"detail": "msg"}`. Anything
 * unparseable comes back under `detail`.
 */
export function fieldErrors(err: unknown): Record<string, string> {
  const msg = err instanceof Error ? err.message : String(err);
  const match = msg.match(/^API \d+: (.+)$/s);
  if (match) {
    try {
      const body = JSON.parse(match[1]);
      if (body && typeof body === "object" && !Array.isArray(body)) {
        return Object.fromEntries(
          Object.entries(body).map(([field, value]) => [
            field,
            Array.isArray(value) ? value.join(" ") : String(value),
          ])
        );
      }
    } catch {
      // not JSON — fall through
    }
  }
  return { detail: "Something went wrong. Please try again." };
}
