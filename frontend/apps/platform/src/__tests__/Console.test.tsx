import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Console } from "../components/Console";
import "../i18n";

const fetchMock = vi.fn();

function json(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

const OPERATOR = { email: "dana@modryn.example", display_name: "Dana" };
const BELLA = {
  slug: "bella",
  name: "בלה כלות",
  status: "active",
  created_at: "2026-08-01T09:30:00Z",
};
const NOA = {
  slug: "noa",
  name: "נועה",
  status: "active",
  created_at: "2026-08-02T09:30:00Z",
};

function listOnly(rows: unknown[] = [BELLA, NOA]) {
  mockFetch((url: string) =>
    url === "/platform/tenants"
      ? Promise.resolve(json(200, { tenants: rows }))
      : Promise.resolve(json(200, { ok: true })),
  );
}

function listCalls(): number {
  return fetchMock.mock.calls.filter((call) => call[0] === "/platform/tenants").length;
}

// F26 added a SECOND fetch to this component's mount. Every mock below routes
// /platform/invites to an empty list unless the test overrides it — a fixture
// change, not an assertion change: every F25 assertion in this file is untouched.
function mockFetch(handler: (url: string) => Promise<Response>) {
  fetchMock.mockImplementation((url: string) =>
    url === "/platform/invites" ? Promise.resolve(json(200, { invites: [] })) : handler(url),
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderConsole() {
  return render(<Console operator={OPERATOR} onSignedOut={() => {}} />);
}

describe("the tenant table", () => {
  it("fetches once per mount and filters client-side", async () => {
    // ⚠ THE POINT OF THE WHOLE DATA DISCIPLINE. Every GET /platform/tenants
    // writes a TENANTS_LISTED row into platform_audit_log — the one audited read
    // in the product — so a filter that refetched would spam the platform's own
    // book with a row per keystroke.
    listOnly();
    renderConsole();
    await screen.findByText("בלה כלות");
    expect(listCalls()).toBe(1);

    await userEvent.type(screen.getByLabelText("סינון לפי שם או כתובת"), "noa");
    await waitFor(() => expect(screen.queryByText("בלה כלות")).not.toBeInTheDocument());
    expect(screen.getByText("נועה")).toBeInTheDocument();
    expect(listCalls()).toBe(1);
  });

  it("says so when nothing matches, without emptying the platform", async () => {
    listOnly();
    renderConsole();
    await screen.findByText("בלה כלות");
    await userEvent.type(screen.getByLabelText("סינון לפי שם או כתובת"), "zzz");
    expect(await screen.findByText("אף בוטיק אינו תואם את הסינון.")).toBeInTheDocument();
    // NOT the EmptyState — that one is reserved for a platform with no boutiques
    // at all, and its copy points at the provision form.
    expect(
      screen.queryByText("אין עדיין בוטיקים במערכת. אפשר להקים את הראשון בטופס שלמטה."),
    ).not.toBeInTheDocument();
  });

  it("renders the true-empty platform's own state", async () => {
    listOnly([]);
    renderConsole();
    expect(
      await screen.findByText("אין עדיין בוטיקים במערכת. אפשר להקים את הראשון בטופס שלמטה."),
    ).toBeInTheDocument();
  });

  it("carries the status as a WORD, never as colour alone", async () => {
    listOnly([BELLA, { ...NOA, status: "suspended" }]);
    renderConsole();
    expect(await screen.findByText("פעיל")).toBeInTheDocument();
    expect(screen.getByText("מושהה")).toBeInTheDocument();
  });

  it("gives a suspended row no suspend action", async () => {
    // There is no un-suspend in this console (spec OUT), so the only thing left
    // to do to a suspended boutique is reset its owner's password.
    listOnly([{ ...BELLA, status: "suspended" }]);
    renderConsole();
    const row = (await screen.findByText("בלה כלות")).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).queryByRole("button", { name: "השהיה" })).toBeNull();
    expect(
      within(row as HTMLElement).getByRole("button", { name: "איפוס סיסמת בעלים" }),
    ).toBeInTheDocument();
  });

  it("uses no sm buttons anywhere (F-W1's 44px floor)", async () => {
    // `Button size="sm"` is min-h-9 = 36px and fails the touch-target floor.
    // Asserted on the rendered class rather than on the prop, because the prop is
    // what a reviewer reads and the class is what a finger hits.
    listOnly();
    renderConsole();
    await screen.findByText("בלה כלות");
    for (const button of screen.getAllByRole("button")) {
      expect(button.className).not.toContain("min-h-9");
      expect(button.className).toContain("min-h-11");
    }
  });
});

describe("suspend", () => {
  it("patches the row locally instead of refetching the list", async () => {
    listOnly();
    renderConsole();
    const row = (await screen.findByText("בלה כלות")).closest("tr") as HTMLElement;
    await userEvent.click(within(row).getByRole("button", { name: "השהיה" }));

    const dialog = await screen.findByRole("dialog");
    // The ONLY red in the flow is the modal's confirm — the row trigger stays
    // plain (declared table-density deviation).
    const confirm = within(dialog).getByRole("button", { name: "השהיה" });
    expect(confirm.className).toContain("bg-danger");
    await userEvent.click(confirm);

    await waitFor(() => expect(screen.getByText("מושהה")).toBeInTheDocument());
    expect(listCalls()).toBe(1);
  });

  it("maps a server refusal onto its own sentence", async () => {
    mockFetch((url: string) =>
      url === "/platform/tenants"
        ? Promise.resolve(json(200, { tenants: [BELLA] }))
        : Promise.resolve(
            json(404, { error: { code: "tenant_not_found", message: "The platform refused." } }),
          ),
    );
    renderConsole();
    const row = (await screen.findByText("בלה כלות")).closest("tr") as HTMLElement;
    await userEvent.click(within(row).getByRole("button", { name: "השהיה" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "השהיה" }));

    expect(
      await screen.findByText("הבוטיק לא נמצא. כדאי לרענן את הרשימה."),
    ).toBeInTheDocument();
  });
});

describe("the provision form", () => {
  // ⚠ SCOPED TO THE FORM. F26's create-invite form reuses these three labels
  // verbatim (its declared deviation — the fields are byte-identical), so an
  // unscoped getByLabelText now matches two controls. Both forms carry
  // `aria-labelledby`, which is what makes each addressable.
  function provisionForm() {
    return within(screen.getByRole("form", { name: "בוטיק חדש" }));
  }

  async function fill(slug: string) {
    await userEvent.type(provisionForm().getByLabelText("כתובת (תת־דומיין)"), slug);
    // NOT «בוטיק חדש» — that is the provision form's own h2, and a row
    // asserted by a string the heading also carries would pass on the heading.
    await userEvent.type(provisionForm().getByLabelText("שם הבוטיק"), "בוטיק של חן");
    await userEvent.type(provisionForm().getByLabelText("אימייל של בעלת הבוטיק"), "o@x.example");
    await userEvent.type(provisionForm().getByLabelText("סיסמה ראשונית"), "first-owner-pw");
  }

  it("appends the row and clears the password on success", async () => {
    listOnly([BELLA]);
    renderConsole();
    await screen.findByText("בלה כלות");
    await fill("chen");
    await userEvent.click(screen.getByRole("button", { name: "הקמת בוטיק" }));

    expect(await screen.findByText("בוטיק של חן")).toBeInTheDocument();
    // ⚠ THE PASSWORD LEAVES MEMORY. The console holds no lasting secret, and the
    // success line never repeats it.
    expect(provisionForm().getByLabelText("סיסמה ראשונית")).toHaveValue("");
    expect(screen.getByText(/הבוטיק הוקם/)).toBeInTheDocument();
    expect(screen.queryByText(/first-owner-pw/)).not.toBeInTheDocument();
    // Appended locally — no second list GET, no second audit row.
    expect(listCalls()).toBe(1);
  });

  it("refuses a reserved slug before any request is fired", async () => {
    listOnly([]);
    renderConsole();
    await screen.findByText("אין עדיין בוטיקים במערכת. אפשר להקים את הראשון בטופס שלמטה.");
    await fill("admin");
    expect(await screen.findByText("הכתובת הזו שמורה למערכת ואינה זמינה.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "הקמת בוטיק" }));
    expect(fetchMock.mock.calls.filter((c) => c[0] === "/platform/tenants/provision")).toHaveLength(
      0,
    );
  });

  it("keeps the typed values when the server refuses", async () => {
    mockFetch((url: string) =>
      url === "/platform/tenants"
        ? Promise.resolve(json(200, { tenants: [] }))
        : Promise.resolve(
            json(409, { error: { code: "slug_taken", message: "The platform refused." } }),
          ),
    );
    renderConsole();
    await screen.findByText("אין עדיין בוטיקים במערכת. אפשר להקים את הראשון בטופס שלמטה.");
    await fill("chen");
    await userEvent.click(screen.getByRole("button", { name: "הקמת בוטיק" }));

    expect(await screen.findByText("הכתובת הזו כבר תפוסה.")).toBeInTheDocument();
    expect(provisionForm().getByLabelText("שם הבוטיק")).toHaveValue("בוטיק של חן");
    expect(provisionForm().getByLabelText("כתובת (תת־דומיין)")).toHaveValue("chen");
  });

  it("falls through to the generic sentence for a code nobody mapped", async () => {
    mockFetch((url: string) =>
      url === "/platform/tenants"
        ? Promise.resolve(json(200, { tenants: [] }))
        : Promise.resolve(
            json(400, { error: { code: "a_new_refusal", message: "Something the server said." } }),
          ),
    );
    renderConsole();
    await screen.findByText("אין עדיין בוטיקים במערכת. אפשר להקים את הראשון בטופס שלמטה.");
    await fill("chen");
    await userEvent.click(screen.getByRole("button", { name: "הקמת בוטיק" }));
    // Degraded, never wrong: the server's own message rather than another code's
    // sentence.
    expect(await screen.findByText("Something the server said.")).toBeInTheDocument();
  });
});

describe("the reset-owner-password dialog", () => {
  it("keeps its values on owner_not_found and repeats no password when done", async () => {
    let resetStatus = 404;
    mockFetch((url: string) => {
      if (url === "/platform/tenants") return Promise.resolve(json(200, { tenants: [BELLA] }));
      if (url === "/platform/tenants/reset-owner-password") {
        return Promise.resolve(
          resetStatus === 404
            ? json(404, { error: { code: "owner_not_found", message: "no" } })
            : json(200, { ok: true }),
        );
      }
      return Promise.resolve(json(200, { ok: true }));
    });
    renderConsole();
    const row = (await screen.findByText("בלה כלות")).closest("tr") as HTMLElement;
    await userEvent.click(within(row).getByRole("button", { name: "איפוס סיסמת בעלים" }));

    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("אימייל של בעלת הבוטיק"), "o@x.example");
    await userEvent.type(within(dialog).getByLabelText("סיסמה חדשה"), "a-new-owner-pw");
    await userEvent.click(within(dialog).getByRole("button", { name: "איפוס סיסמה" }));

    expect(
      await within(dialog).findByText("האימייל אינו תואם את בעלת הבוטיק הרשומה."),
    ).toBeInTheDocument();
    // Still open, still holding both values — re-typing a password to fix a typo
    // in the email address is a punishment for the server's own check.
    expect(within(dialog).getByLabelText("אימייל של בעלת הבוטיק")).toHaveValue("o@x.example");
    expect(within(dialog).getByLabelText("סיסמה חדשה")).toHaveValue("a-new-owner-pw");

    resetStatus = 200;
    await userEvent.click(within(dialog).getByRole("button", { name: "איפוס סיסמה" }));
    expect(
      await screen.findByText("הסיסמה אופסה. יש למסור אותה לבעלת הבוטיק בעצמך."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/a-new-owner-pw/)).not.toBeInTheDocument();
  });

  it("shows no danger button — a password reset is not destructive", async () => {
    listOnly([BELLA]);
    renderConsole();
    const row = (await screen.findByText("בלה כלות")).closest("tr") as HTMLElement;
    await userEvent.click(within(row).getByRole("button", { name: "איפוס סיסמת בעלים" }));
    const dialog = await screen.findByRole("dialog");
    for (const button of within(dialog).getAllByRole("button")) {
      expect(button.className).not.toContain("bg-danger");
    }
  });
});

// --- F26: invites, and the one-time link panel -------------------------------

const OPEN_INVITE = {
  id: "11111111-1111-4111-8111-111111111111",
  slug: "chen",
  name: "בוטיק של חן",
  owner_email: "chen@x.example",
  created_by: "dana@modryn.example",
  expires_at: "2099-08-20T09:04:00Z",
  redeemed_at: null,
  created_at: "2026-08-06T09:04:00Z",
};
const REDEEMED_INVITE = {
  ...OPEN_INVITE,
  id: "22222222-2222-4222-8222-222222222222",
  slug: "noa",
  name: "נועה",
  redeemed_at: "2026-08-07T10:00:00Z",
};
const EXPIRED_INVITE = {
  ...OPEN_INVITE,
  id: "33333333-3333-4333-8333-333333333333",
  slug: "gal",
  name: "גל",
  expires_at: "2020-01-01T09:00:00Z",
};
const CODE = "s3cret-invite-code-value";
const CREATED = {
  code: CODE,
  join_url: `https://admin.modryn.co.il/platform/join?code=${CODE}`,
  invite: OPEN_INVITE,
};

function withInvites(rows: unknown[], rest: (url: string) => Promise<Response> = () =>
  Promise.resolve(json(200, { ok: true }))) {
  fetchMock.mockImplementation((url: string) => {
    if (url === "/platform/tenants") return Promise.resolve(json(200, { tenants: [] }));
    if (url === "/platform/invites" ) return Promise.resolve(json(200, { invites: rows }));
    return rest(url);
  });
}

function createForm() {
  return within(screen.getByRole("form", { name: "הזמנה חדשה" }));
}

async function fillInvite(slug: string) {
  await userEvent.type(createForm().getByLabelText("כתובת (תת־דומיין)"), slug);
  await userEvent.type(createForm().getByLabelText("שם הבוטיק"), "בוטיק של חן");
  await userEvent.type(createForm().getByLabelText("אימייל של בעלת הבוטיק"), "chen@x.example");
}

describe("the invites table", () => {
  it("words every status and renders NO code column", async () => {
    // A2 rule 7 at the surface that would show it. The wire type has no code
    // field; this asserts the table cannot render one even if it did.
    withInvites([OPEN_INVITE, REDEEMED_INVITE, EXPIRED_INVITE]);
    renderConsole();

    const table = await screen.findByRole("table", { name: /רשימת ההזמנות/ });
    expect(within(table).getByText("פתוחה")).toBeInTheDocument();
    expect(within(table).getByText("נוצלה")).toBeInTheDocument();
    // Derived client-side: the server stores an instant, not a state.
    expect(within(table).getByText("פג תוקף")).toBeInTheDocument();
    expect(within(table).getAllByRole("columnheader")).toHaveLength(6);
    expect(within(table).queryByText(/קוד/)).not.toBeInTheDocument();

    // Only the OPEN row carries an action — there is nothing left to do to a
    // redeemed or expired invite.
    expect(within(table).getAllByRole("button", { name: "ביטול ההזמנה" })).toHaveLength(1);
  });

  it("removes the row on a confirmed revoke, without refetching", async () => {
    withInvites([OPEN_INVITE]);
    renderConsole();
    await screen.findByText("בוטיק של חן");

    await userEvent.click(screen.getByRole("button", { name: "ביטול ההזמנה" }));
    const dialog = await screen.findByRole("dialog");
    // «חזרה», never «ביטול» beside a confirm that reads «ביטול ההזמנה» (A4).
    expect(within(dialog).getByRole("button", { name: "חזרה" })).toBeInTheDocument();
    // The ONLY red in the flow is the footer confirm; the row trigger is plain.
    const confirm = within(dialog).getByRole("button", { name: "ביטול ההזמנה" });
    expect(confirm.className).toContain("bg-danger");

    await userEvent.click(confirm);
    await waitFor(() => expect(screen.queryByText("בוטיק של חן")).not.toBeInTheDocument());
    expect(
      fetchMock.mock.calls.filter((call) => call[0] === "/platform/invites"),
    ).toHaveLength(1);
  });
});

describe("the one-time link panel", () => {
  it("replaces the create form, and the form is ABSENT while it is open", async () => {
    // A2 rule 3: a second create cannot clobber an unread code, and the panel
    // cannot scroll out of sight behind a form she is retyping into.
    fetchMock.mockImplementation((url: string, init?: { method?: string }) => {
      if (url === "/platform/tenants") return Promise.resolve(json(200, { tenants: [] }));
      if (url === "/platform/invites") {
        return Promise.resolve(
          init?.method === "POST" ? json(200, CREATED) : json(200, { invites: [] }),
        );
      }
      return Promise.resolve(json(200, { ok: true }));
    });
    renderConsole();
    await screen.findByRole("form", { name: "הזמנה חדשה" });
    await fillInvite("chen");
    await userEvent.click(screen.getByRole("button", { name: "יצירת הזמנה" }));

    await screen.findByRole("heading", { name: "ההזמנה נוצרה", level: 3 });
    expect(screen.queryByRole("form", { name: "הזמנה חדשה" })).not.toBeInTheDocument();

    // readOnly, NOT disabled — a disabled control is unselectable, so manual
    // copy would be impossible on exactly the machine with no clipboard API.
    const field = screen.getByLabelText("קישור ההזמנה");
    expect(field).toHaveValue(CREATED.join_url);
    expect(field).toHaveAttribute("readonly");
    expect(field).not.toBeDisabled();
    // Never an <a href> (A2 r5): a click would put a live code in history and
    // in a referrer.
    expect(screen.queryByRole("link", { name: /קישור/ })).not.toBeInTheDocument();
    // The dismiss is LAST in DOM order, so a thumb at the bottom of the panel
    // does not land on it before the copy control.
    const buttons = screen.getAllByRole("button");
    const copyAt = buttons.findIndex((b) => b.textContent === "העתקת הקישור");
    const dismissAt = buttons.findIndex((b) => b.textContent === "שמרתי את הקישור — סגירה");
    expect(copyAt).toBeGreaterThanOrEqual(0);
    expect(dismissAt).toBeGreaterThan(copyAt);
  });

  it("loses the code on dismiss, from the DOM and from every storage", async () => {
    // ⚠ A2 RULE 7 AS BEHAVIOUR. After dismissal the code must be recoverable
    // from nowhere: not the DOM, not sessionStorage, not localStorage. The list
    // response never carries it either, so the table cannot re-render it.
    const sessionSet = vi.spyOn(Storage.prototype, "setItem");
    fetchMock.mockImplementation((url: string, init?: { method?: string }) => {
      if (url === "/platform/tenants") return Promise.resolve(json(200, { tenants: [] }));
      if (url === "/platform/invites") {
        return Promise.resolve(
          init?.method === "POST" ? json(200, CREATED) : json(200, { invites: [] }),
        );
      }
      return Promise.resolve(json(200, { ok: true }));
    });
    renderConsole();
    await screen.findByRole("form", { name: "הזמנה חדשה" });
    await fillInvite("chen");
    await userEvent.click(screen.getByRole("button", { name: "יצירת הזמנה" }));
    await screen.findByRole("heading", { name: "ההזמנה נוצרה", level: 3 });
    expect(document.body.innerHTML).toContain(CODE);

    await userEvent.click(screen.getByRole("button", { name: "שמרתי את הקישור — סגירה" }));

    await screen.findByRole("form", { name: "הזמנה חדשה" });
    expect(document.body.innerHTML).not.toContain(CODE);
    // The spy is on Storage.prototype, so it covers sessionStorage AND
    // localStorage in one assertion — jsdom does not always expose both.
    expect(sessionSet).not.toHaveBeenCalled();
    expect(window.sessionStorage.length).toBe(0);
    // …and the form comes back EMPTY: the values were cleared behind the panel.
    expect(createForm().getByLabelText("כתובת (תת־דומיין)")).toHaveValue("");
    sessionSet.mockRestore();
  });

  it("speaks the copy result and keeps the link selectable when copying fails", async () => {
    fetchMock.mockImplementation((url: string, init?: { method?: string }) => {
      if (url === "/platform/tenants") return Promise.resolve(json(200, { tenants: [] }));
      if (url === "/platform/invites") {
        return Promise.resolve(
          init?.method === "POST" ? json(200, CREATED) : json(200, { invites: [] }),
        );
      }
      return Promise.resolve(json(200, { ok: true }));
    });
    // No navigator.clipboard is the real failure mode — an insecure origin, or
    // an older browser. The manual path has to be STATED, not discovered.
    vi.stubGlobal("navigator", { ...navigator, clipboard: undefined });
    renderConsole();
    await screen.findByRole("form", { name: "הזמנה חדשה" });
    await fillInvite("chen");
    await userEvent.click(screen.getByRole("button", { name: "יצירת הזמנה" }));
    await screen.findByRole("heading", { name: "ההזמנה נוצרה", level: 3 });

    await userEvent.click(screen.getByRole("button", { name: "העתקת הקישור" }));
    expect(
      await screen.findByText("לא הצלחנו להעתיק את הקישור. אפשר לסמן אותו ולהעתיק ידנית."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("קישור ההזמנה")).not.toBeDisabled();
  });
});
