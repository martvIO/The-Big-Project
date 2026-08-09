import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { StaffMember } from "../api";
import { StaffSection } from "../components/StaffSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      listStaff: vi.fn(),
      createStaff: vi.fn(),
      updateStaff: vi.fn(),
      deactivateStaff: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const listStaff = vi.mocked(api.listStaff);
const createStaff = vi.mocked(api.createStaff);
const updateStaff = vi.mocked(api.updateStaff);
const deactivateStaff = vi.mocked(api.deactivateStaff);

const ME = "11111111-1111-1111-1111-111111111111";
const HER = "22222222-2222-2222-2222-222222222222";

function member(overrides: Partial<StaffMember> = {}): StaffMember {
  return {
    id: HER,
    email: "dana@bella.example",
    display_name: "דנה",
    role: "shift_manager",
    created_at: "2026-07-30T09:00:00Z",
    // F38's six. Defaulted to the absent state so every test written before
    // this feature keeps describing the row it meant to describe.
    phone: null,
    start_date: null,
    last_day: null,
    shift_manager_eligible: false,
    photo_url: null,
    photo_confirmed_at: null,
    ...overrides,
  };
}

const OWNER = member({ id: ME, email: "sara@bella.example", display_name: "שרה", role: "owner" });

// StaffSection renders inside ConsoleShell's <main>, which owns the console's
// single sr-only <h1>. The axe harness reproduces that frame rather than
// scanning a headless fragment.
function renderInShell(node: ReactNode) {
  return render(
    <main>
      <h1 className="sr-only">ניהול הבוטיק</h1>
      {node}
    </main>,
  );
}

function renderSection() {
  return renderInShell(<StaffSection staffId={ME} />);
}

// The create form carries the SAME labels and the same two role words as the
// inline edit, so every row-level query is scoped to its <li>. Unscoped queries
// here are ambiguous by construction, not by accident.
function rowFor(name: string): HTMLElement {
  const node = screen.getByText(name).closest("li");
  expect(node).not.toBeNull();
  return node as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
});

// --- list states ---

describe("StaffSection list", () => {
  it("shows a skeleton while the list is in flight", () => {
    listStaff.mockReturnValue(new Promise(() => {}));
    const { container } = renderSection();
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders a load failure in the outage register, not the danger one", async () => {
    listStaff.mockRejectedValue(new ApiError(503, "UNKNOWN", "boom"));
    renderSection();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("לא הצלחנו לטעון את רשימת הצוות כרגע.");
    // Outage copy is muted, not red: nothing the owner did is wrong.
    expect(alert.className).toContain("text-ink-muted");
  });

  it("renders each staffer's name, address and role word", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    expect(await screen.findByText("דנה")).toBeInTheDocument();
    expect(screen.getByText("שרה")).toBeInTheDocument();
    expect(screen.getByText("dana@bella.example")).toBeInTheDocument();
    // The WORD carries the role — the test asserts the word, never the class.
    // Scoped to the rows: the create form's <select> carries the same two words.
    expect(within(rowFor("שרה")).getByText("בעלת הבוטיק")).toBeInTheDocument();
    expect(within(rowFor("דנה")).getByText("אחראית משמרת")).toBeInTheDocument();
  });

  it("marks the acting owner's own row and offers her no deactivate control", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    expect(screen.getByText("זו את")).toBeInTheDocument();
    // The server refuses a self-deactivate with a 409; not drawing the button is
    // the cosmetic half of that, so she is never offered a door that refuses.
    expect(screen.getAllByRole("button", { name: /^השבתה/ })).toHaveLength(1);
    // …and the one that IS drawn is the OTHER woman's.
    expect(screen.getByRole("button", { name: "השבתה — דנה" })).toBeInTheDocument();
  });

  // The walkthrough's finding: `aria-label`, `aria-labelledby` and
  // `aria-describedby` were ALL null on both row buttons, so a boutique with
  // seven staff rendered seven identical «עריכה» and six identical «השבתה» in
  // one list — AND ONE OF THEM DEACTIVATES A COLLEAGUE'S ACCESS. A screen-reader
  // user tabbing the list, or anyone driving it by speech, had nothing to tell
  // them apart. It also broke the console's OWN convention: the floor, waitlist
  // and atelier panels all render «{action} — {name}».
  it("names every row control after the woman it acts on, in three-row shape", async () => {
    const rows = [
      OWNER,
      member(),
      member({ id: "33333333-3333-3333-3333-333333333333", display_name: "יעל" }),
    ];
    listStaff.mockResolvedValue(rows);
    renderSection();
    await screen.findByText("יעל");

    for (const row of rows) {
      // ⚠ `name:` is an ACCESSIBLE-NAME match, so this fails on the shipped
      // version rather than merely finding the visible text: with no aria-label
      // the name is «עריכה» for all three.
      expect(
        screen.getByRole("button", { name: `עריכה — ${row.display_name}` }),
      ).toBeInTheDocument();
    }
    // WCAG 2.5.3: the accessible name STARTS with the visible label, so speech
    // input can say what it reads.
    for (const button of screen.getAllByRole("button", { name: /^עריכה/ })) {
      expect(button.textContent).toBe("עריכה");
    }
    // No two controls in the list share a name — the actual defect, stated as
    // the property rather than as three lookups.
    const names = screen
      .getAllByRole("button", { name: /^(עריכה|השבתה)/ })
      .map((button) => button.getAttribute("aria-label"));
    expect(new Set(names).size).toBe(names.length);
    expect(names).toHaveLength(5); // 3 edits + 2 deactivates (never her own)
  });
});

// --- bidi ---

describe("StaffSection bidi", () => {
  it("isolates the Latin address ltr and the Hebrew name without a direction", async () => {
    listStaff.mockResolvedValue([member()]);
    const { container } = renderSection();
    await screen.findByText("דנה");

    const email = screen.getByText("dana@bella.example");
    expect(email.tagName).toBe("BDI");
    expect(email).toHaveAttribute("dir", "ltr");

    // A bare <bdi> on the name: dir="ltr" on a Hebrew name is itself a bidi
    // defect, so isolation without a forced direction is the whole point.
    const name = screen.getByText("דנה");
    expect(name.tagName).toBe("BDI");
    expect(name).not.toHaveAttribute("dir");
    expect(container.querySelector("bdi[dir='rtl']")).toBeNull();
  });
});

// --- create ---

describe("StaffSection create", () => {
  it("says out loud that the password is the owner's to deliver", async () => {
    listStaff.mockResolvedValue([OWNER]);
    renderSection();
    await screen.findByText("שרה");
    expect(
      screen.getByText("יש למסור את הסיסמה לעובדת בעצמך. המערכת אינה מעבירה אותה לאיש."),
    ).toBeInTheDocument();
  });

  it("posts the wire body and appends the new row without refetching", async () => {
    listStaff.mockResolvedValue([OWNER]);
    createStaff.mockResolvedValue(member());
    renderSection();
    await screen.findByText("שרה");

    fireEvent.change(screen.getByLabelText("אימייל"), {
      target: { value: "dana@bella.example" },
    });
    fireEvent.change(screen.getByLabelText("שם לתצוגה"), { target: { value: "דנה" } });
    fireEvent.change(screen.getByLabelText("סיסמה"), { target: { value: "a-long-enough-pw" } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה לצוות" }));

    await waitFor(() =>
      expect(createStaff).toHaveBeenCalledWith({
        email: "dana@bella.example",
        display_name: "דנה",
        role: "shift_manager",
        password: "a-long-enough-pw",
      }),
    );
    expect(await screen.findByText("דנה")).toBeInTheDocument();
    // One fetch, at mount: the list is patched from the mutation response, so
    // the two views cannot disagree.
    expect(listStaff).toHaveBeenCalledTimes(1);
  });

  it("uses a new-password autocomplete so the browser cannot offer her own credential", async () => {
    listStaff.mockResolvedValue([OWNER]);
    renderSection();
    await screen.findByText("שרה");
    const password = screen.getByLabelText("סיסמה");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "new-password");
  });

  it("blocks a short password client-side without calling the API", async () => {
    listStaff.mockResolvedValue([OWNER]);
    renderSection();
    await screen.findByText("שרה");

    fireEvent.change(screen.getByLabelText("אימייל"), { target: { value: "d@b.example" } });
    fireEvent.change(screen.getByLabelText("שם לתצוגה"), { target: { value: "דנה" } });
    fireEvent.change(screen.getByLabelText("סיסמה"), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה לצוות" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("הסיסמה חייבת להכיל לפחות 10 תווים");
    expect(createStaff).not.toHaveBeenCalled();
  });

  // The browser's own type="email" check passes `dana@bella` — WHATWG makes the
  // dot in the domain optional — and pydantic's EmailStr then answers «value is
  // not a valid email address: The part after the @-sign is not valid...», which
  // this form would render verbatim into an RTL console.
  it("blocks an address the server would refuse in English, without calling the API", async () => {
    listStaff.mockResolvedValue([OWNER]);
    renderSection();
    await screen.findByText("שרה");

    fireEvent.change(screen.getByLabelText("אימייל"), { target: { value: "dana@bella" } });
    fireEvent.change(screen.getByLabelText("שם לתצוגה"), { target: { value: "דנה" } });
    fireEvent.change(screen.getByLabelText("סיסמה"), { target: { value: "a-long-enough-pw" } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה לצוות" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("כתובת האימייל אינה תקינה");
    expect(createStaff).not.toHaveBeenCalled();
  });

  it("blocks an empty address client-side", async () => {
    listStaff.mockResolvedValue([OWNER]);
    renderSection();
    await screen.findByText("שרה");

    fireEvent.change(screen.getByLabelText("שם לתצוגה"), { target: { value: "דנה" } });
    fireEvent.change(screen.getByLabelText("סיסמה"), { target: { value: "a-long-enough-pw" } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה לצוות" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("יש להזין כתובת אימייל");
    expect(createStaff).not.toHaveBeenCalled();
  });

  it("renders a duplicate address in Hebrew, not the server's English", async () => {
    listStaff.mockResolvedValue([OWNER]);
    createStaff.mockRejectedValue(
      new ApiError(409, "DUPLICATE_EMAIL", "A staff member with this email already exists."),
    );
    renderSection();
    await screen.findByText("שרה");

    fireEvent.change(screen.getByLabelText("אימייל"), { target: { value: "d@b.example" } });
    fireEvent.change(screen.getByLabelText("שם לתצוגה"), { target: { value: "דנה" } });
    fireEvent.change(screen.getByLabelText("סיסמה"), { target: { value: "a-long-enough-pw" } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה לצוות" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "כתובת האימייל הזו כבר משויכת לאשת צוות פעילה.",
    );
  });
});

// --- inline edit ---

describe("StaffSection inline edit", () => {
  function openEditFor(name: string): HTMLElement {
    const row = rowFor(name);
    fireEvent.click(within(row).getByRole("button", { name: /^עריכה/ }));
    return row;
  }

  it("renames a staffer and patches the row from the response", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    updateStaff.mockResolvedValue(member({ display_name: "דנה כהן" }));
    renderSection();
    await screen.findByText("דנה");
    const row = openEditFor("דנה");

    fireEvent.change(within(row).getByLabelText("שם לתצוגה"), { target: { value: "דנה כהן" } });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    await waitFor(() =>
      expect(updateStaff).toHaveBeenCalledWith(HER, { display_name: "דנה כהן" }),
    );
    expect(await screen.findByText("דנה כהן")).toBeInTheDocument();
  });

  it("sends only the fields that actually moved", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    updateStaff.mockResolvedValue(member({ role: "owner" }));
    renderSection();
    await screen.findByText("דנה");
    const row = openEditFor("דנה");

    fireEvent.change(within(row).getByLabelText("תפקיד"), { target: { value: "owner" } });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    // The name did not change and the password box is empty, so neither is sent:
    // an all-unchanged patch is a no-op the server answers 200 without auditing.
    await waitFor(() => expect(updateStaff).toHaveBeenCalledWith(HER, { role: "owner" }));
  });

  it("uses a native select for the role", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = openEditFor("דנה");
    expect(within(row).getByLabelText("תפקיד").tagName).toBe("SELECT");
  });

  it("renders the last-owner refusal in Hebrew", async () => {
    listStaff.mockResolvedValue([OWNER, member({ role: "owner" })]);
    updateStaff.mockRejectedValue(
      new ApiError(409, "LAST_OWNER_REQUIRED", "The boutique must always have at least one owner."),
    );
    renderSection();
    await screen.findByText("דנה");
    const row = openEditFor("דנה");

    fireEvent.change(within(row).getByLabelText("תפקיד"), { target: { value: "shift_manager" } });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לבוטיק חייבת להיות בעלת בוטיק אחת לפחות.",
    );
  });

  it("falls through to the server's own message for an unmapped code", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    updateStaff.mockRejectedValue(new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts."));
    renderSection();
    await screen.findByText("דנה");
    const row = openEditFor("דנה");

    fireEvent.change(within(row).getByLabelText("שם לתצוגה"), { target: { value: "דנה כהן" } });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts.");
  });
});

// --- her own row ---

describe("StaffSection self edit", () => {
  function openOwnEdit(): HTMLElement {
    const row = rowFor("שרה");
    fireEvent.click(within(row).getByRole("button", { name: /^עריכה/ }));
    return row;
  }

  it("offers no role control on her own row", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = openOwnEdit();
    // Self-demotion is a lockout the console cannot undo: the router is
    // owner-only, so she could not promote herself back.
    expect(within(row).queryByLabelText("תפקיד")).toBeNull();
    expect(within(row).getByLabelText("שם לתצוגה")).toBeInTheDocument();
  });

  it("asks for the current password only when she types a new one", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = openOwnEdit();

    expect(within(row).queryByLabelText("הסיסמה הנוכחית שלך")).toBeNull();
    fireEvent.change(within(row).getByLabelText("סיסמה חדשה"), {
      target: { value: "a-brand-new-pw" },
    });
    expect(within(row).getByLabelText("הסיסמה הנוכחית שלך")).toBeInTheDocument();
  });

  it("sends the current password with a self rotation", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    updateStaff.mockResolvedValue(OWNER);
    renderSection();
    await screen.findByText("דנה");
    const row = openOwnEdit();

    fireEvent.change(within(row).getByLabelText("סיסמה חדשה"), {
      target: { value: "a-brand-new-pw" },
    });
    fireEvent.change(within(row).getByLabelText("הסיסמה הנוכחית שלך"), {
      target: { value: "the-old-one" },
    });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    await waitFor(() =>
      expect(updateStaff).toHaveBeenCalledWith(ME, {
        password: "a-brand-new-pw",
        current_password: "the-old-one",
      }),
    );
  });

  it("renders a wrong current password in the field's own slot, never in English", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    updateStaff.mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "current_password is required and must match"),
    );
    renderSection();
    await screen.findByText("דנה");
    const row = openOwnEdit();

    fireEvent.change(within(row).getByLabelText("סיסמה חדשה"), {
      target: { value: "a-brand-new-pw" },
    });
    fireEvent.change(within(row).getByLabelText("הסיסמה הנוכחית שלך"), {
      target: { value: "nope" },
    });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "הסיסמה הנוכחית שגויה. יש להזין את הסיסמה הנוכחית כדי לשנות אותה.",
    );
    expect(screen.queryByText(/current_password/)).toBeNull();
  });

  it("never sends a current password when resetting someone else's", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    updateStaff.mockResolvedValue(member());
    renderSection();
    await screen.findByText("דנה");
    const row = rowFor("דנה");
    fireEvent.click(within(row).getByRole("button", { name: /^עריכה/ }));

    fireEvent.change(within(row).getByLabelText("סיסמה חדשה"), {
      target: { value: "reset-for-her" },
    });
    expect(within(row).queryByLabelText("הסיסמה הנוכחית שלך")).toBeNull();
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    await waitFor(() =>
      expect(updateStaff).toHaveBeenCalledWith(HER, { password: "reset-for-her" }),
    );
  });
});

// --- deactivate ---

describe("StaffSection deactivate", () => {
  function openConfirm() {
    fireEvent.click(within(rowFor("דנה")).getByRole("button", { name: /^השבתה/ }));
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect((dialog as HTMLDialogElement).open).toBe(true);
    return dialog;
  }

  it("confirms before removing and names the staffer", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    deactivateStaff.mockResolvedValue({ ok: true });
    renderSection();
    await screen.findByText("דנה");

    const dialog = openConfirm();
    expect(dialog).toHaveTextContent("דנה");
    // The two facts that make it safe to tap: it bites immediately, and it is
    // undoable by re-creating the account.
    expect(dialog).toHaveTextContent("בפעולה הבאה שלה");
    expect(deactivateStaff).not.toHaveBeenCalled();

    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "השבתה" }));
    await waitFor(() => expect(deactivateStaff).toHaveBeenCalledWith(HER));
    await waitFor(() => expect(screen.queryByText("דנה")).toBeNull());
  });

  // The one screen whose whole job is naming the right person before a
  // destructive action. ProvisioningService seeds every founding owner with
  // display_name = owner_email, so a Latin run inside this Hebrew sentence is
  // the norm here and reorders at its neutral edges without an isolate.
  it("isolates the name in a bare <bdi>, like the list row does", async () => {
    listStaff.mockResolvedValue([OWNER, member({ display_name: "dana (bella)." })]);
    renderSection();
    await screen.findByText("dana (bella).");

    fireEvent.click(
      within(rowFor("dana (bella).")).getByRole("button", { name: /^השבתה/ }),
    );
    const dialog = screen.getByRole("dialog", { hidden: true });
    const isolated = within(dialog as HTMLElement).getByText("dana (bella).");
    expect(isolated.tagName).toBe("BDI");
    expect(isolated).not.toHaveAttribute("dir");
    // And the markup is markup, not text the owner reads.
    expect(dialog).not.toHaveTextContent("<bdi>");
  });

  it("cancelling removes nothing and returns focus to the trigger", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");

    const dialog = openConfirm();
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "ביטול" }));

    await waitFor(() => expect((dialog as HTMLDialogElement).open).toBe(false));
    expect(deactivateStaff).not.toHaveBeenCalled();
    expect(within(rowFor("דנה")).getByRole("button", { name: /^השבתה/ })).toHaveFocus();
  });

  it("moves focus to the heading once the row is gone", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    deactivateStaff.mockResolvedValue({ ok: true });
    renderSection();
    await screen.findByText("דנה");

    const dialog = openConfirm();
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "השבתה" }));

    // The trigger unmounts with its row, so restoring focus to it would land on
    // <body> — the heading is the nearest thing that still exists.
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 2, name: "צוות" })).toHaveFocus(),
    );
  });

  it("renders a refused self-deactivate in Hebrew", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    deactivateStaff.mockRejectedValue(
      new ApiError(409, "STAFF_SELF_MANAGE", "You cannot deactivate your own account."),
    );
    renderSection();
    await screen.findByText("דנה");

    const dialog = openConfirm();
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "השבתה" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "אי אפשר לשנות את התפקיד של עצמך או להשבית את עצמך.",
    );
  });

  it("renders a mid-session demotion in Hebrew rather than the server's English 403", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    deactivateStaff.mockRejectedValue(
      new ApiError(403, "NOT_AUTHORIZED", "This action is not available for your account."),
    );
    renderSection();
    await screen.findByText("דנה");

    const dialog = openConfirm();
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "השבתה" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "הפעולה הזו זמינה לבעלת הבוטיק בלבד.",
    );
  });
});

// --- accessibility: IS 5568 / WCAG 2.0 AA is a legal requirement ---

describe("StaffSection accessibility", () => {
  it("passes axe with zero violations on the loaded list", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    const { container } = renderSection();
    await screen.findByText("דנה");
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations with a row open for editing", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    const { container } = renderSection();
    await screen.findByText("דנה");
    fireEvent.click(within(rowFor("דנה")).getByRole("button", { name: /^עריכה/ }));
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations with the confirm dialog open", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    const { container } = renderSection();
    await screen.findByText("דנה");
    fireEvent.click(within(rowFor("דנה")).getByRole("button", { name: /^השבתה/ }));
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("goes h2 then h3 with no skipped level and no tab role anywhere", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    const { container } = renderSection();
    await screen.findByText("דנה");

    // The shipped Modal always renders its own <h2> title into the DOM, open or
    // not, so the outline is read outside the dialog.
    const levels = [...container.querySelectorAll("h1, h2, h3, h4, h5, h6")]
      .filter((node) => node.closest("dialog") === null)
      .map((node) => node.tagName);
    expect(levels).toEqual(["H1", "H2", "H3"]);
    expect(container.querySelector("[role='tab']")).toBeNull();
  });

  it("gives every control a real label", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    const { container } = renderSection();
    await screen.findByText("דנה");
    for (const field of container.querySelectorAll("input, select")) {
      expect(field.id).toBeTruthy();
      expect(container.querySelector(`label[for='${field.id}']`)).not.toBeNull();
    }
  });
});

describe("StaffSection carries the five roles F57 added", () => {
  it("renders «תופרת» for a seamstress rather than «אחראית משמרת»", async () => {
    // ⚠ THE TEST THAT FAILS AGAINST THE UN-FIXED TERNARY. Until F57,
    // `roleWord` was `role === "owner" ? roleOwner : roleShiftManager`, which
    // returns «אחראית משמרת» for ANYTHING that is not owner. Widening StaffRole
    // without fixing it labels every seamstress a shift manager on this screen —
    // a defect this feature CREATES, not one it inherits.
    listStaff.mockResolvedValue([
      OWNER,
      member({ role: "seamstress", display_name: "נועה" }),
    ]);
    renderInShell(<StaffSection staffId={ME} />);

    await screen.findByText("נועה");
    // Scoped to HER ROW: the role words also appear as <option>s in the edit
    // form, so an unscoped query is ambiguous rather than wrong.
    expect(within(rowFor("נועה")).getByText("תופרת")).toBeInTheDocument();
    expect(within(rowFor("נועה")).queryByText("אחראית משמרת")).toBeNull();
  });

  it.each([
    ["reception", "קבלה"],
    ["sales_assistant", "יועצת מכירות"],
    ["seamstress", "תופרת"],
  ])("renders %s as its own word", async (role, word) => {
    listStaff.mockResolvedValue([OWNER, member({ role: role as StaffMember["role"] })]);
    renderInShell(<StaffSection staffId={ME} />);

    await screen.findByText("דנה");
    expect(within(rowFor("דנה")).getByText(word)).toBeInTheDocument();
  });

  it("offers all five roles in EVERY role select", async () => {
    // Both selects — the create form's and the inline edit form's — widen from
    // ROLE_OPTIONS, so neither can silently keep offering two.
    listStaff.mockResolvedValue([OWNER, member()]);
    renderInShell(<StaffSection staffId={ME} />);
    await screen.findByText("דנה");

    fireEvent.click(within(rowFor("דנה")).getByRole("button", { name: /^עריכה/ }));

    const selects = await screen.findAllByLabelText("תפקיד");
    expect(selects.length).toBeGreaterThan(0);
    for (const select of selects) {
      expect(within(select).getAllByRole("option").map((option) => option.textContent)).toEqual([
        "בעלת הבוטיק",
        "אחראית משמרת",
        "קבלה",
        "יועצת מכירות",
        "תופרת",
      ]);
    }
  });
});
