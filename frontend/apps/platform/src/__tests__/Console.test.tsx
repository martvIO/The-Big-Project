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
  fetchMock.mockImplementation((url: string) =>
    url === "/platform/tenants"
      ? Promise.resolve(json(200, { tenants: rows }))
      : Promise.resolve(json(200, { ok: true })),
  );
}

function listCalls(): number {
  return fetchMock.mock.calls.filter((call) => call[0] === "/platform/tenants").length;
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
    fetchMock.mockImplementation((url: string) =>
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
  async function fill(slug: string) {
    await userEvent.type(screen.getByLabelText("כתובת (תת־דומיין)"), slug);
    // NOT «בוטיק חדש» — that is the provision form's own h2, and a row
    // asserted by a string the heading also carries would pass on the heading.
    await userEvent.type(screen.getByLabelText("שם הבוטיק"), "בוטיק של חן");
    await userEvent.type(screen.getByLabelText("אימייל של בעלת הבוטיק"), "o@x.example");
    await userEvent.type(screen.getByLabelText("סיסמה ראשונית"), "first-owner-pw");
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
    expect(screen.getByLabelText("סיסמה ראשונית")).toHaveValue("");
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
    fetchMock.mockImplementation((url: string) =>
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
    expect(screen.getByLabelText("שם הבוטיק")).toHaveValue("בוטיק של חן");
    expect(screen.getByLabelText("כתובת (תת־דומיין)")).toHaveValue("chen");
  });

  it("falls through to the generic sentence for a code nobody mapped", async () => {
    fetchMock.mockImplementation((url: string) =>
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
    fetchMock.mockImplementation((url: string) => {
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
