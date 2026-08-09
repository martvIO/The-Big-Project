import type { Page } from "@playwright/test";

// The platform console's Playwright interception harness — `fixtures/manage.ts`
// in shape, and deliberately so: the console is a third app with the same
// bootstrap-on-`me()` pattern, so the trap, the recorder and the reply queue are
// all the same problem one app over.
//
// ⚠ **IT STUBS THE API, SO IT PROVES THE CONSOLE AND NOT THE CONTRACT.** A
// backend change that renames a payload key passes every test here while
// breaking production. `test_platform_console_api.py` (the code→status table)
// and `test_platform_console_db.py` (the lifecycle under real Postgres) are the
// contract side; this is the journey and accessibility instrument. The wire
// shapes below are hand-mirrored from `apps/platform/src/api.ts` on purpose —
// importing the app's types would drag its module graph into the e2e typecheck,
// which is manage.ts's and storefront.spec.ts's rule too.
//
// **How it authenticates: it does not.** `App.tsx` bootstraps on `api.me()` and
// renders `<LoginPanel/>` on a rejection, so fulfilling `GET /platform/auth/me`
// with a 200 body is the whole of "signed in" — no cookie, no login POST, no
// session table, and no host fence (the preview server is `localhost`).

export const PLATFORM = "http://localhost:4175/platform/";

// ⚠ **THE SAME TRAP `manage.ts` EXISTS TO MAKE UN-STEPPABLE-ON: a route on
// `**​/platform/**` ALSO MATCHES THE APP ITSELF.** `apps/platform` builds with
// `base: "/platform/"`, so `/platform/index.html`, `/platform/assets/*.js` and
// `/platform/favicon.svg` all live under that prefix — one broad glob serves a
// blank page with no error anywhere.
//
// The guard is the backend's own rule rather than a per-feature glob list: a
// path is an API path exactly when its SECOND SEGMENT is one the /platform
// routers declare. That set is `apps/platform/vite.config.ts`'s `PLATFORM_API`
// alternation verbatim, and `backend/tests/test_spa_serving.py` derives it from
// the live route table and asserts the two agree — so this cannot drift from the
// server without that test going red first.
const API_FAMILIES = new Set(["auth", "tenants"]);

function isPlatformApi(pathname: string): boolean {
  // ["", "platform", family, …]. A bare "/platform/" splits to a third element
  // of "", which is in no family — the shell's own URL is never intercepted.
  const segments = pathname.split("/");
  return segments[1] === "platform" && API_FAMILIES.has(segments[2] ?? "");
}

export interface Reply {
  status: number;
  body: unknown;
}

export function ok(body: unknown): Reply {
  return { status: 200, body };
}

// The house error envelope. The message is ENGLISH on purpose — every backend
// message is, and the console selects its Hebrew by CODE. A fixture carrying
// Hebrew here would hide a UI that painted the server's sentence onto a
// Hebrew-only screen, which is precisely what one test below checks for.
export function refuse(status: number, code: string): Reply {
  return { status, body: { error: { code, message: `${code} from the fixture.` } } };
}

// **The design, not a fallback.** An unstubbed call must fail LOUDLY — as a
// rendered Hebrew error the test can see — rather than reaching `vite preview`'s
// proxy to a port with nothing on it, where the failure reads as a flake.
const NOT_FOUND: Reply = {
  status: 404,
  body: { error: { code: "NOT_FOUND", message: "Nothing is stubbed at this path." } },
};

// A one-element queue is a constant; a two-element one is "this happens once,
// then that" — which is what a mutation journey needs.
function take(queue: Reply[]): Reply {
  return queue.length > 1 ? (queue.shift() as Reply) : queue[0];
}

export interface RecordedRequest {
  method: string;
  path: string;
  body: unknown;
}

export interface Recorder {
  all: RecordedRequest[];
  of(path: string): RecordedRequest[];
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

export function operator(overrides: Partial<Operator> = {}): Operator {
  return { email: "dana@modryn.example", display_name: "דנה", ...overrides };
}

export function tenant(overrides: Partial<Tenant> = {}): Tenant {
  return {
    slug: "bella",
    name: "בלה כלות",
    status: "active",
    created_at: "2026-08-01T09:30:00Z",
    ...overrides,
  };
}

export interface PlatformApiOptions {
  /** Omit to boot SIGNED OUT — `me` then answers 401 and the login panel renders. */
  operator?: Operator | null;
  tenants?: Tenant[];
  replies?: Record<string, Reply[]>;
}

export async function installPlatformApi(
  page: Page,
  options: PlatformApiOptions = {},
): Promise<Recorder> {
  const identity = options.operator === undefined ? operator() : options.operator;
  const replies: Record<string, Reply[]> = {
    "/platform/auth/me":
      identity === null
        ? [refuse(401, "NOT_AUTHENTICATED")]
        : [ok(identity)],
    "/platform/tenants": [ok({ tenants: options.tenants ?? [] })],
    ...options.replies,
  };

  const all: RecordedRequest[] = [];

  await page.route(
    (url) => isPlatformApi(url.pathname),
    async (route) => {
      const request = route.request();
      const { pathname } = new URL(request.url());
      const raw = request.postData();
      let body: unknown = null;
      if (raw !== null) {
        try {
          body = JSON.parse(raw);
        } catch {
          body = raw;
        }
      }
      all.push({ method: request.method(), path: pathname, body });

      // The method-qualified key first, so `/platform/tenants` can answer a list
      // to GET and something else to a POST that shares the prefix.
      const queue = replies[`${request.method()} ${pathname}`] ?? replies[pathname];
      const reply = queue === undefined ? NOT_FOUND : take(queue);
      await route.fulfill({
        status: reply.status,
        headers: { "content-type": "application/json", "cache-control": "no-store" },
        body: JSON.stringify(reply.body),
      });
    },
  );

  return { all, of: (path: string) => all.filter((entry) => entry.path === path) };
}
