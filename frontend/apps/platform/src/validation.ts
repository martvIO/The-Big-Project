// A MIRROR of Backend/app/tenancy/slugs.py, and deliberately only a mirror: the
// server is authoritative and answers `invalid_or_reserved_slug` regardless of
// what happens here. This exists so the operator learns about a typo while
// typing it rather than after a round trip that also writes a
// TENANT_PROVISION_FAILED audit row.
//
// ⚠ Backend/tests/test_frontend_constant_parity.py is the pattern that keeps
// copies like this honest; the reserved list below is RESERVED_SLUGS verbatim.
const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

export const RESERVED_SLUGS = [
  "admin",
  "api",
  "app",
  "assets",
  "cdn",
  "docs",
  "mail",
  "staging",
  "static",
  "status",
  "support",
  "www",
] as const;

export type SlugProblem = "invalid" | "reserved" | null;

export function slugProblem(slug: string): SlugProblem {
  if (slug === "") return null;
  if (!SLUG_RE.test(slug)) return "invalid";
  if ((RESERVED_SLUGS as readonly string[]).includes(slug)) return "reserved";
  return null;
}

// F26 design B1: the join field accepts a PASTED FULL LINK, not just a bare
// code. The link carries the code in its FRAGMENT (`…/platform/join#code=…`, so
// no request line ever holds it), which this already handles: the marker search
// is position-independent and `#` is only a terminator.
// The owner was given a link, so a link is what she will paste, and
// refusing it would spend a failures-only limiter attempt on a formatting
// mistake — at 5 per 15 minutes, three of those lock her out of her own
// boutique.
//
// Here rather than in JoinPanel.tsx so that file exports components only (fast
// refresh), and because a pure string function is worth testing without a DOM.
export function extractCode(pasted: string): string {
  const trimmed = pasted.trim();
  const marker = trimmed.indexOf("code=");
  if (marker === -1) return trimmed;
  const tail = trimmed.slice(marker + "code=".length);
  return decodeURIComponent(tail.split(/[&#\s]/, 1)[0] ?? "");
}
