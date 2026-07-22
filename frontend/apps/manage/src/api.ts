// Typed fetch helper for the /manage owner console. Wire format is the
// backend's snake_case verbatim (no case conversion layer — the OpenAPI
// client wrapper is F10 scope). Cookies carry the session, so every call
// sends credentials: "include"; errors arrive in the house shape
// {"error": {"code", "message"}} and are surfaced as ApiError.

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

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : FALLBACK_ERROR_MESSAGE;
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

// --- wire types (mirror backend/app/boutique/schemas.py + app/auth/schemas.py) ---

export interface Staff {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

export interface ProfileSettings {
  phone?: string;
  address?: string;
  description?: string;
  maps_url?: string;
}

export interface ToggleSettings {
  deposits_enabled?: boolean;
  brides_only?: boolean;
}

export interface Settings {
  profile: ProfileSettings;
  toggles: ToggleSettings;
}

export interface UpdateSettingsRequest {
  profile?: ProfileSettings;
  toggles?: ToggleSettings;
}

export type AppointmentAudience = "all" | "brides_only";

export interface AppointmentTypeInput {
  name: string;
  duration_minutes: number;
  audience: AppointmentAudience;
  deposit_required: boolean;
  deposit_amount_agorot: number | null;
  sort_order: number;
}

export interface AppointmentType extends AppointmentTypeInput {
  id: string;
}

export interface WeeklyRuleInput {
  day_of_week: number;
  open_time: string;
  close_time: string;
  capacity: number;
}

export interface AvailabilityRule extends WeeklyRuleInput {
  id: string;
}

export interface AvailabilityExceptionInput {
  date: string;
  open_time: string | null;
  close_time: string | null;
  note: string | null;
}

export interface AvailabilityException extends AvailabilityExceptionInput {
  id: string;
}

export interface Availability {
  rules: AvailabilityRule[];
  exceptions: AvailabilityException[];
}

export interface CreateTermsRequest {
  terms_text: string;
  refundable_until_hours_before: number;
  forfeit_percent: number;
}

export interface TermsVersion extends CreateTermsRequest {
  id: string;
  version: number;
  created_by: string;
  created_at: string;
}

export interface TermsHistory {
  current: TermsVersion | null;
  versions: TermsVersion[];
  total: number;
  offset: number;
  limit: number;
}

export interface OkResponse {
  ok: boolean;
}

// --- endpoints ---

export const api = {
  login(email: string, password: string): Promise<Staff> {
    return apiFetch("/manage/auth/login", { method: "POST", body: { email, password } });
  },
  logout(): Promise<OkResponse> {
    return apiFetch("/manage/auth/logout", { method: "POST" });
  },
  me(): Promise<Staff> {
    return apiFetch("/manage/auth/me");
  },

  getSettings(): Promise<Settings> {
    return apiFetch("/manage/settings");
  },
  updateSettings(body: UpdateSettingsRequest): Promise<Settings> {
    return apiFetch("/manage/settings", { method: "PUT", body });
  },

  listAppointmentTypes(): Promise<AppointmentType[]> {
    return apiFetch("/manage/appointment-types");
  },
  createAppointmentType(body: AppointmentTypeInput): Promise<AppointmentType> {
    return apiFetch("/manage/appointment-types", { method: "POST", body });
  },
  updateAppointmentType(id: string, body: AppointmentTypeInput): Promise<AppointmentType> {
    return apiFetch(`/manage/appointment-types/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body,
    });
  },
  archiveAppointmentType(id: string): Promise<OkResponse> {
    return apiFetch(`/manage/appointment-types/${encodeURIComponent(id)}`, { method: "DELETE" });
  },

  getAvailability(): Promise<Availability> {
    return apiFetch("/manage/availability");
  },
  replaceWeeklyRules(rules: WeeklyRuleInput[]): Promise<AvailabilityRule[]> {
    return apiFetch("/manage/availability/rules", { method: "PUT", body: { rules } });
  },
  addAvailabilityException(body: AvailabilityExceptionInput): Promise<AvailabilityException> {
    return apiFetch("/manage/availability/exceptions", { method: "POST", body });
  },
  removeAvailabilityException(id: string): Promise<OkResponse> {
    return apiFetch(`/manage/availability/exceptions/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  getTerms(): Promise<TermsHistory> {
    return apiFetch("/manage/terms");
  },
  createTermsVersion(body: CreateTermsRequest): Promise<TermsVersion> {
    return apiFetch("/manage/terms", { method: "POST", body });
  },
};
