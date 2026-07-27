// Allowlist of URL schemes safe to place in a tenant-controlled href. An
// allowlist (must START with a safe scheme) beats a denylist: browsers strip
// leading control chars / whitespace ("java\tscript:"), so denylists are
// bypassable. `javascript:`/`data:`/`vbscript:` never match and are dropped.
const SAFE_SCHEME = /^(https?:|tel:|mailto:)/i;

// Returns the URL if its scheme is safe, otherwise undefined so the caller can
// degrade to non-link text. Tenant-supplied values (maps_url, waze) flow here
// before ever reaching an href — React does NOT neutralise a javascript: href.
export function safeHref(url?: string | null): string | undefined {
  const trimmed = url?.trim();
  return trimmed && SAFE_SCHEME.test(trimmed) ? trimmed : undefined;
}
