// Typed fetch helper for the public storefront. Three GETs, no mutations. Wire
// format is the backend's snake_case verbatim; errors arrive in the house shape
// {"error": {"code", "message"}} and are surfaced as ApiError.
//
// Deliberately a local copy of apps/manage's helper rather than a shared
// package: the two differ on credentials, and hoisting them into
// @boutique/api-client is a cleanup with no consumer pressure yet.

export const FALLBACK_ERROR_MESSAGE = "אירעה שגיאה בלתי צפויה. נסי שוב.";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

// An unknown id, an archived (soft-deleted) dress and another tenant's dress are
// all indistinguishable 404s by design — every one of them renders
// "השמלה כבר לא זמינה".
//
// A malformed id is the same miss. /dress/xyz out of a mistyped or truncated
// link fails FastAPI's UUID coercion, which the platform normalises to
// 400 VALIDATION_ERROR — semantically "no such dress", not "the server broke".
// Without this it rendered dress.error plus a Retry button that re-issues the
// same 400 forever. The dress detail is the storefront's only path-parameter
// endpoint, so this is the only shape a VALIDATION_ERROR can take here.
export function isNotFound(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  return error.status === 404 || (error.status === 400 && error.code === "VALIDATION_ERROR");
}

function extractError(body: unknown): { code: string; message: string } | null {
  if (typeof body !== "object" || body === null) {
    return null;
  }
  const envelope = (body as { error?: unknown }).error;
  if (typeof envelope !== "object" || envelope === null) {
    return null;
  }
  const { code, message } = envelope as { code?: unknown; message?: unknown };
  if (typeof message !== "string") {
    return null;
  }
  return { code: typeof code === "string" ? code : "UNKNOWN", message };
}

export async function apiFetch<T>(path: string): Promise<T> {
  // credentials: "omit" — this is a public surface. A session cookie sent to an
  // unauthenticated endpoint is a cookie that ends up in an access log, and
  // nothing here is per-visitor.
  const response = await fetch(path, { method: "GET", credentials: "omit" });
  if (!response.ok) {
    let extracted: { code: string; message: string } | null = null;
    try {
      extracted = extractError(await response.json());
    } catch {
      // Non-JSON error body (proxy/HTML page) — fall through to the fallback.
    }
    throw new ApiError(
      response.status,
      extracted?.code ?? "UNKNOWN",
      extracted?.message ?? FALLBACK_ERROR_MESSAGE,
    );
  }
  return (await response.json()) as T;
}

// --- wire types (mirror backend/app/storefront/schemas.py) ---
//
// Every field below is always present; nullable ones serialise as null, never
// omitted. NOTE what is absent and must stay absent: price_visible, quantity,
// out_of_stock, total_quantity, variant_count, archived, media_uploads_enabled,
// media_slots_remaining, capacity, toggles. Those are manage-only.

export interface PublicMedia {
  // Presigned GET, 900s TTL — bearer material. null means no bucket configured
  // or signing failed.
  url: string | null;
  url_expires_at: string | null;
}

export interface PublicDress {
  id: string;
  name: string;
  // null = hidden by the owner OR never set. The storefront cannot tell the two
  // apart, by design, and renders both as "מחיר בתיאום".
  price_agorot: number | null;
  // The only badge on the storefront. There is no out-of-stock badge.
  reserved: boolean;
  cover: PublicMedia | null;
}

export interface PublicDressListResponse {
  items: PublicDress[];
  total: number;
  offset: number;
  // Always 24 — server-pinned, the client cannot ask for more.
  limit: number;
}

export interface PublicVariant {
  size_label: string;
  // quantity > 0, computed server-side. Raw counts are boutique-confidential and
  // never reach the wire.
  available: boolean;
}

export interface PublicDressDetailResponse {
  id: string;
  name: string;
  description: string | null;
  price_agorot: number | null;
  reserved: boolean;
  variants: PublicVariant[];
  // Ready photos in gallery order; media[0] is the cover.
  media: PublicMedia[];
}

export interface PublicProfile {
  phone: string | null;
  address: string | null;
  description: string | null;
  maps_url: string | null;
}

export interface PublicHoursRule {
  // 0 = Sunday … 6 = Saturday (Israeli week).
  day_of_week: number;
  open_time: string; // "10:00:00"
  close_time: string; // "19:00:00"
}

export interface PublicHoursException {
  date: string; // "2026-08-26"
  // Both null = closed all day; both set = special hours.
  open_time: string | null;
  close_time: string | null;
  note: string | null;
}

export interface PublicBoutiqueResponse {
  // The tenant's display name, not the slug. This is the <h1>.
  name: string;
  profile: PublicProfile;
  rules: PublicHoursRule[];
  exceptions: PublicHoursException[];
}

// --- endpoints ---

export const api = {
  // offset is the only parameter the server accepts; limit is pinned at 24.
  listDresses(offset = 0): Promise<PublicDressListResponse> {
    return apiFetch(`/storefront/dresses?offset=${String(offset)}`);
  },
  getDress(dressId: string): Promise<PublicDressDetailResponse> {
    return apiFetch(`/storefront/dresses/${encodeURIComponent(dressId)}`);
  },
  getBoutique(): Promise<PublicBoutiqueResponse> {
    return apiFetch("/storefront/boutique");
  },
};

// The footer needs the boutique block on every page and the body needs it again
// on / and /about. One promise per page load covers both; unlike the dress
// endpoints this response carries no signed URLs, so there is nothing to go
// stale within a session.
let boutiqueOnce: Promise<PublicBoutiqueResponse> | null = null;

export function getBoutiqueOnce(): Promise<PublicBoutiqueResponse> {
  boutiqueOnce ??= api.getBoutique().catch((error: unknown) => {
    // Drop the rejected promise, otherwise every retry replays the same failure.
    boutiqueOnce = null;
    throw error;
  });
  return boutiqueOnce;
}

export function resetBoutiqueCache(): void {
  boutiqueOnce = null;
}
