/**
 * The post-login `?next=` target, restricted to a same-site path. Anything
 * else falls back. Browsers treat "\" like "/", so "/\evil.com" is the same
 * protocol-relative off-site URL as "//evil.com" and must be rejected too.
 */
export function safeNext(raw: string | null | undefined, fallback = "/"): string {
  if (!raw || !raw.startsWith("/")) return fallback;
  const second = raw.charAt(1);
  return second === "/" || second === "\\" ? fallback : raw;
}
