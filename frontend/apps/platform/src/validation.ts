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
