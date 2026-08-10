// Typed fetch client for the platform console. Wire format is the backend's
// snake_case verbatim (no case-conversion layer — the manage app's decision,
// inherited). Cookies carry the session, so every call sends
// credentials: "include"; errors arrive in the house shape
// {"error": {"code", "message"}} and are surfaced as ApiError.
//
// ⚠ THE CODE IS THE CONTRACT. The console maps five refusal codes to their own
// Hebrew sentences (design deck §6) and falls through to `errorMessage()` for
// anything else, so `ApiError.code` — not its message — is what the UI branches
// on. The server's message is English and is never rendered.

export const FALLBACK_ERROR_MESSAGE = "אירעה שגיאה בלתי צפויה. אפשר לנסות שוב.";

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

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : FALLBACK_ERROR_MESSAGE;
}

// ⚠ THE MID-SESSION 401 IS SIGNALLED FROM HERE, and it has to be. A 401 is not a
// per-call refusal — it is the whole session ending — but every call site in the
// console catches its own ApiError to render a refusal sentence, so the rejection
// never reaches the window and a listener on `unhandledrejection` (which is what
// this was) fires for none of the documented trigger paths. The fetch that
// produced the status is the one place all four call sites route through.
//
// The subscriber (App) registers only while an operator is signed in, so the
// bootstrap `me()` 401 and a refused login — both 401s on the login screen — are
// not session expiries.
let sessionExpiredHandler: (() => void) | null = null;

export function onSessionExpired(handler: (() => void) | null): void {
  sessionExpiredHandler = handler;
}

function extractError(body: unknown): { code: string; message: string } | null {
  if (typeof body !== "object" || body === null) return null;
  const envelope = (body as { error?: unknown }).error;
  if (typeof envelope !== "object" || envelope === null) return null;
  const { code, message } = envelope as { code?: unknown; message?: unknown };
  if (typeof message !== "string") return null;
  return { code: typeof code === "string" ? code : "UNKNOWN", message };
}

export async function apiFetch<T>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const { method = "GET", body } = init;
  const response = await fetch(path, {
    method,
    credentials: "include",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) sessionExpiredHandler?.();
    let extracted: ReturnType<typeof extractError> = null;
    try {
      extracted = extractError(await response.json());
    } catch {
      // Non-JSON error body (a proxy's HTML page) — fall through to the fallback.
    }
    throw new ApiError(
      response.status,
      extracted?.code ?? "UNKNOWN",
      extracted?.message ?? FALLBACK_ERROR_MESSAGE,
    );
  }
  return (await response.json()) as T;
}

export interface Operator {
  email: string;
  display_name: string;
}

export interface Tenant {
  slug: string;
  name: string;
  status: string;
  created_at: string;
}

export interface ProvisionInput {
  slug: string;
  name: string;
  owner_email: string;
  owner_password: string;
}

// F26. `Invite` is the console table's row and it carries NO code and no hash —
// the wire type mirrors the server's `InviteRow`, where that absence is asserted
// by a test. The raw code exists on `InviteCreated` only, once (design A2 r7).
export interface Invite {
  id: string;
  slug: string;
  name: string;
  owner_email: string;
  created_by: string;
  expires_at: string;
  redeemed_at: string | null;
  created_at: string;
}

export interface InviteCreated {
  code: string;
  join_url: string;
  invite: Invite;
}

export interface InvitePreview {
  slug: string;
  name: string;
  owner_email: string;
}

export interface CreateInviteInput {
  slug: string;
  name: string;
  owner_email: string;
}

export const api = {
  me: () => apiFetch<Operator>("/platform/auth/me"),
  login: (email: string, password: string) =>
    apiFetch<Operator>("/platform/auth/login", { method: "POST", body: { email, password } }),
  logout: () => apiFetch<{ ok: boolean }>("/platform/auth/logout", { method: "POST" }),
  listTenants: async () => (await apiFetch<{ tenants: Tenant[] }>("/platform/tenants")).tenants,
  provision: (input: ProvisionInput) =>
    apiFetch<{ ok: boolean }>("/platform/tenants/provision", { method: "POST", body: input }),
  suspend: (slug: string) =>
    apiFetch<{ ok: boolean }>("/platform/tenants/suspend", { method: "POST", body: { slug } }),
  resetOwnerPassword: (slug: string, owner_email: string, new_password: string) =>
    apiFetch<{ ok: boolean }>("/platform/tenants/reset-owner-password", {
      method: "POST",
      body: { slug, owner_email, new_password },
    }),

  // --- F26 invites (operator) ---
  listInvites: async () =>
    (await apiFetch<{ invites: Invite[] }>("/platform/invites")).invites,
  createInvite: (input: CreateInviteInput) =>
    apiFetch<InviteCreated>("/platform/invites", { method: "POST", body: input }),
  revokeInvite: (id: string) =>
    apiFetch<{ ok: boolean }>("/platform/invites/revoke", { method: "POST", body: { id } }),

  // --- F26 join (anonymous) ---
  //
  // ⚠ THE ONLY TWO CALLS IN THIS CLIENT THAT RUN WITHOUT A SESSION. They still
  // go through `apiFetch`, so `credentials: "include"` sends a console cookie if
  // one happens to exist — harmless, because the server's join router carries no
  // operator dependency and reads none.
  //
  // The code travels in the QUERY STRING for the preview because it is a read,
  // and in the BODY for the redeem. Neither is logged by this app, and the
  // console's own history never sees either: the operator copies the link, she
  // never opens it (design A2 r5).
  previewInvite: (code: string) =>
    apiFetch<InvitePreview>(`/platform/join/invite?code=${encodeURIComponent(code)}`),
  redeemInvite: (code: string, owner_password: string) =>
    apiFetch<{ slug: string; manage_url: string }>("/platform/join/redeem", {
      method: "POST",
      body: { code, owner_password },
    }),
};
