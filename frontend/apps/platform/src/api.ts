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
};
