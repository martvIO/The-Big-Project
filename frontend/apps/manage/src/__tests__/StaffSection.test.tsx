import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { StaffMember } from "../api";
import { StaffSection } from "../components/StaffSection";
import { todayJerusalem } from "../lib/jerusalem";

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
      staffPhotoPresign: vi.fn(),
      staffPhotoConfirm: vi.fn(),
      staffPhotoDelete: vi.fn(),
    },
    uploadToStorage: vi.fn(),
  };
});

const { api, ApiError } = await import("../api");
const listStaff = vi.mocked(api.listStaff);
const createStaff = vi.mocked(api.createStaff);
const updateStaff = vi.mocked(api.updateStaff);
const deactivateStaff = vi.mocked(api.deactivateStaff);
const staffPhotoPresign = vi.mocked(api.staffPhotoPresign);
const staffPhotoConfirm = vi.mocked(api.staffPhotoConfirm);
const staffPhotoDelete = vi.mocked(api.staffPhotoDelete);
const uploadToStorage = vi.mocked((await import("../api")).uploadToStorage);

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
    expect(screen.getAllByRole("button", { name: /^סיום העסקה/ })).toHaveLength(1);
    // …and the one that IS drawn is the OTHER woman's.
    expect(screen.getByRole("button", { name: "סיום העסקה — דנה" })).toBeInTheDocument();
  });

  // The walkthrough's finding: `aria-label`, `aria-labelledby` and
  // `aria-describedby` were ALL null on both row buttons, so a boutique with
  // seven staff rendered seven identical «עריכה» and six identical «סיום העסקה» in
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
      .getAllByRole("button", { name: /^(עריכה|סיום העסקה)/ })
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
        // F38. ALWAYS sent, unlike phone and start_date below: an unanswered
        // "may she be slotted as shift manager" is a no, not a third state.
        shift_manager_eligible: false,
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
    // ⚠ NOT `TOO_MANY_ATTEMPTS` — F38 put that in MAPPED_CODES, which is exactly
    // the drift this test exists to notice from the other side. Any code the Set
    // does not carry does; `INTERNAL_ERROR` is one the section will never map.
    listStaff.mockResolvedValue([OWNER, member()]);
    updateStaff.mockRejectedValue(new ApiError(500, "INTERNAL_ERROR", "Too many attempts."));
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
    fireEvent.click(within(rowFor("דנה")).getByRole("button", { name: /^סיום העסקה/ }));
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
    // The two IMMEDIATE facts: access stops on her next action, and the photo
    // goes now. What is retained and what is erased later is the retention
    // note's job, asserted in its own test below.
    expect(dialog).toHaveTextContent("בפעולה הבאה שלה");
    expect(deactivateStaff).not.toHaveBeenCalled();

    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "סיום העסקה" }));
    // F38: the leaving date rides the call, defaulted to today JERUSALEM. A
    // blank would silently exempt her from the retention clock forever.
    await waitFor(() => expect(deactivateStaff).toHaveBeenCalledWith(HER, todayJerusalem()));
    // Her ROW is gone. Her NAME is not: F38's role="status" line is the only
    // feedback there is once the row leaves the list, and it names her inside a
    // bare <bdi>, so an unscoped queryByText would now match that instead.
    await waitFor(() => expect(screen.queryByRole("button", { name: /^עריכה — דנה/ })).toBeNull());
    expect(screen.getByRole("status")).toHaveTextContent("רישומי העבודה שלה נשמרו");
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
      within(rowFor("dana (bella).")).getByRole("button", { name: /^סיום העסקה/ }),
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
    expect(within(rowFor("דנה")).getByRole("button", { name: /^סיום העסקה/ })).toHaveFocus();
  });

  it("moves focus to the heading once the row is gone", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    deactivateStaff.mockResolvedValue({ ok: true });
    renderSection();
    await screen.findByText("דנה");

    const dialog = openConfirm();
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "סיום העסקה" }));

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
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "סיום העסקה" }));

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
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "סיום העסקה" }));

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
    fireEvent.click(within(rowFor("דנה")).getByRole("button", { name: /^סיום העסקה/ }));
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

// --- F38: the HR fields, the photo control and the offboard dialog ---
//
// Plan G2-G6. Until this block, the whole Manage half of F38 was unreachable
// from the product: `validateStaffPhotoFile` had zero call sites outside its own
// test, `api.staffPhoto*` were never invoked, and `deactivateStaff`'s `lastDay`
// argument was never passed anywhere real.

function editorFor(name: string): HTMLElement {
  const row = rowFor(name);
  fireEvent.click(within(row).getByRole("button", { name: /^עריכה/ }));
  return row;
}

// Only the three properties `validateStaffPhotoFile` and the presign body read,
// so nothing here needs a File polyfill beyond what jsdom already gives.
function imageFile(overrides: Partial<{ name: string; type: string; size: number }> = {}): File {
  const file = new File(["x"], overrides.name ?? "dana.jpg", {
    type: overrides.type ?? "image/jpeg",
  });
  Object.defineProperty(file, "size", { value: overrides.size ?? 400_000 });
  return file;
}

function pick(row: HTMLElement, label: string, file: File) {
  const input = within(row).getByLabelText(label, { exact: false }) as HTMLInputElement;
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  fireEvent.change(input);
  return input;
}

const PRESIGN = {
  url: "https://bucket.example/",
  fields: { policy: "opaque" },
  expires_in: 300,
  max_bytes: 400_000,
};

describe("StaffSection profile fields", () => {
  it("sends only the HR fields that actually moved", async () => {
    listStaff.mockResolvedValue([
      OWNER,
      member({ phone: "+972501111111", start_date: "2026-01-01" }),
    ]);
    updateStaff.mockResolvedValue(member({ shift_manager_eligible: true }));
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    // Name, role, phone and start date all resent UNCHANGED — F51's audit-honesty
    // rule reaching the new fields, and the inline form posts every field on
    // every save, so this is the ordinary case rather than the exotic one.
    fireEvent.click(within(row).getByLabelText("יכולה לנהל משמרת"));
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    await waitFor(() =>
      expect(updateStaff).toHaveBeenCalledWith(HER, { shift_manager_eligible: true }),
    );
  });

  it("sends an EMPTY phone rather than dropping it, which is the only way to clear one", async () => {
    // ⚠ `undefined` already means "not sent" on this API, so a form that coerced
    // "" to undefined would make the clear unreachable from the product and a
    // staffer who asked for her number to come off could not be obliged until
    // the seven-year scrub.
    listStaff.mockResolvedValue([OWNER, member({ phone: "+972501111111" })]);
    updateStaff.mockResolvedValue(member({ phone: null }));
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    fireEvent.change(within(row).getByLabelText("טלפון"), { target: { value: "" } });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    await waitFor(() => expect(updateStaff).toHaveBeenCalledWith(HER, { phone: "" }));
  });

  it("says plainly that the number is contact-only and not a way in", async () => {
    // Spec C1. Staff sign in with email + password through the unchanged
    // /manage/auth/login, and a phone field on a staff row reads like a second
    // login unless the form says otherwise.
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");
    expect(within(row).getByText(/מספר ליצירת קשר בלבד/)).toBeInTheDocument();
  });

  it("renders eligibility as muted words on the row and never as a second Badge", async () => {
    listStaff.mockResolvedValue([OWNER, member({ shift_manager_eligible: true })]);
    const { container } = renderSection();
    await screen.findByText("דנה");
    const row = rowFor("דנה");

    expect(within(row).getByText("יכולה לנהל משמרת")).toBeInTheDocument();
    // ONE pill per row, so the pill means one thing (F36's ruling). The avatar
    // fallback is rounded-full too and is aria-hidden, hence the exclusion.
    expect(row.querySelectorAll("span.rounded-full:not([aria-hidden])")).toHaveLength(1);
    expect(container.querySelectorAll("img")).toHaveLength(0);
  });

  it("says the checkbox is neither a role nor a permission", async () => {
    // O4: F38 stores the boolean and enforces nothing; F40 is its only consumer.
    // A checkbox called «יכולה לנהל משמרת» beside a role select reads as a role
    // unless the description says it is not.
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");
    expect(within(row).getByText(/אינו משנה את התפקיד ואינו משנה הרשאות/)).toBeInTheDocument();
  });
});

describe("StaffSection photo", () => {
  it("runs presign, POST and confirm, and patches the row from the confirm response", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    staffPhotoPresign.mockResolvedValue(PRESIGN);
    uploadToStorage.mockResolvedValue(undefined);
    staffPhotoConfirm.mockResolvedValue(
      member({ photo_url: "https://bucket.example/k?sig", photo_confirmed_at: "2026-08-09T09:00:00Z" }),
    );
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    pick(row, "תמונת פרופיל", imageFile());

    await waitFor(() =>
      expect(staffPhotoPresign).toHaveBeenCalledWith(HER, {
        content_type: "image/jpeg",
        byte_size: 400_000,
      }),
    );
    // The middle call is NOT optional: the object is not hers until confirm
    // verifies its magic bytes server-side.
    await waitFor(() => expect(staffPhotoConfirm).toHaveBeenCalledWith(HER));
    expect(uploadToStorage).toHaveBeenCalledWith(PRESIGN, expect.anything());
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("התמונה נוספה."));
    // `alt=""` maps to role="presentation", so this is a DOM query by design and
    // not a getByRole that would silently never match.
    expect(row.querySelector("img")).toHaveAttribute("src", "https://bucket.example/k?sig");
  });

  it("refuses an over-cap file client-side, with no request at all", async () => {
    // The bound is MIRRORED (validation.ts ↔ auth/photo.py), and the mirror is
    // what makes the immediate Hebrew honest: without it a 3 MiB photo would
    // travel, come back a 400, and land as the server's English sentence.
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    pick(row, "תמונת פרופיל", imageFile({ size: 3_000_000 }));

    expect(await within(row).findByRole("alert")).toHaveTextContent("גדולה מ-2MB");
    expect(staffPhotoPresign).not.toHaveBeenCalled();
  });

  it("gives HEIC its own message, because saving as JPG is an action she can take", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    // Safari hands over an EMPTY type for HEIC, so the extension is the fallback.
    pick(row, "תמונת פרופיל", imageFile({ name: "IMG_0001.HEIC", type: "" }));

    expect(await within(row).findByRole("alert")).toHaveTextContent("HEIC");
    expect(staffPhotoPresign).not.toHaveBeenCalled();
  });

  it("keeps the previous photo rendering when a replace fails, and offers a retry", async () => {
    listStaff.mockResolvedValue([
      OWNER,
      member({ photo_url: "https://bucket.example/old?sig", photo_confirmed_at: "2026-08-01T09:00:00Z" }),
    ]);
    staffPhotoPresign.mockResolvedValue(PRESIGN);
    uploadToStorage.mockResolvedValue(undefined);
    staffPhotoConfirm.mockRejectedValue(
      new ApiError(400, "MEDIA_MISMATCH", "the uploaded file is not a valid image"),
    );
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    pick(row, "החלפת תמונת פרופיל", imageFile());

    // Mapped Hebrew, never the server's English — and the LIVE triple was never
    // touched, so the cell still shows the photo the board is showing.
    expect(await within(row).findByRole("alert")).toHaveTextContent("הקובץ אינו תמונה תקינה.");
    expect(row.querySelector("img")).toHaveAttribute("src", "https://bucket.example/old?sig");
    expect(within(row).getByRole("button", { name: "נסי שוב" })).toBeInTheDocument();
  });

  it("maps an unconfigured bucket to the same sentence as an unavailable one", async () => {
    // The owner cannot tell the two apart and does not need to — her next action
    // is the same either way.
    listStaff.mockResolvedValue([OWNER, member()]);
    staffPhotoPresign.mockRejectedValue(
      new ApiError(503, "MEDIA_NOT_CONFIGURED", "Media storage is not configured."),
    );
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    pick(row, "תמונת פרופיל", imageFile());

    expect(await within(row).findByRole("alert")).toHaveTextContent("אחסון התמונות אינו זמין כרגע");
  });

  it("maps the dedicated presign throttle to Hebrew", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    staffPhotoPresign.mockRejectedValue(
      new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts. Try again later."),
    );
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    pick(row, "תמונת פרופיל", imageFile());

    expect(await within(row).findByRole("alert")).toHaveTextContent("יותר מדי העלאות בזמן קצר");
  });

  it("announces the PPL purpose line at capture, through the input's own description", async () => {
    // ⚠ THE ONLY PLACE the purpose limitation is ever shown to anyone, and the
    // platform's stated operational mitigation for PPL Amendment 13 (spec O1).
    // In the `help` slot rather than a footnote so aria-describedby announces it
    // BEFORE a file is chosen, to keyboard and screen-reader users alike.
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    const input = within(row).getByLabelText("תמונת פרופיל", { exact: false });
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    const described = (describedBy ?? "")
      .split(" ")
      .map((id) => document.getElementById(id)?.textContent ?? "")
      .join(" ");
    expect(described).toContain("התמונה משמשת לזיהוי בלוח המשמרת ובכרטיסי הצוות בלבד.");
    expect(described).toContain("עד 2MB");
  });

  it("is a real, visible, focusable file input and never a display:none shim", async () => {
    // MediaGallery's discipline: a hidden input plus a label shim breaks
    // Safari/VoiceOver and hides the disabled reason. `multiple` is absent —
    // one photo per person.
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    const input = within(row).getByLabelText("תמונת פרופיל", { exact: false }) as HTMLInputElement;
    expect(input.type).toBe("file");
    expect(input.multiple).toBe(false);
    expect(input.accept).toBe("image/jpeg,image/png,image/webp");
    expect(input.className).not.toContain("hidden");
  });

  it("confirms before removing, then clears the cell from the delete response", async () => {
    listStaff.mockResolvedValue([
      OWNER,
      member({ photo_url: "https://bucket.example/k?sig", photo_confirmed_at: "2026-08-01T09:00:00Z" }),
    ]);
    staffPhotoDelete.mockResolvedValue(member());
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");

    fireEvent.click(within(row).getByRole("button", { name: "הסרת תמונה" }));
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog).toHaveTextContent("להסיר את התמונה?");
    expect(dialog).toHaveTextContent("ולא ניתן לשחזר אותה");
    expect(staffPhotoDelete).not.toHaveBeenCalled();

    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "הסרה" }));
    await waitFor(() => expect(staffPhotoDelete).toHaveBeenCalledWith(HER));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("התמונה הוסרה."));
  });

  it("offers no remove control when there is no photo to remove", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");
    expect(within(row).queryByRole("button", { name: "הסרת תמונה" })).toBeNull();
  });

  it("uses ONE dialog for both confirms rather than mounting a second", async () => {
    // R3. A second <Modal> would duplicate the focus-restore effect that exists
    // because the trigger unmounts under the open dialog.
    listStaff.mockResolvedValue([
      OWNER,
      member({ photo_url: "https://bucket.example/k?sig", photo_confirmed_at: "2026-08-01T09:00:00Z" }),
    ]);
    renderSection();
    await screen.findByText("דנה");
    expect(screen.getAllByRole("dialog", { hidden: true })).toHaveLength(1);
  });
});

describe("StaffSection offboarding", () => {
  function openOffboard() {
    fireEvent.click(within(rowFor("דנה")).getByRole("button", { name: /^סיום העסקה/ }));
    return screen.getByRole("dialog", { hidden: true });
  }

  it("defaults the last day to today in Jerusalem", async () => {
    // A BLANK would silently exempt her from the retention clock forever: the
    // policy's predicate needs `last_day IS NOT NULL`, so NULL does not mean
    // "unknown", it means "never scrub this person".
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");

    const dialog = openOffboard();
    expect(within(dialog as HTMLElement).getByLabelText("יום עבודה אחרון")).toHaveValue(
      todayJerusalem(),
    );
  });

  it("states plainly what is kept and what is erased later", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    renderSection();
    await screen.findByText("דנה");

    const dialog = openOffboard();
    expect(dialog).toHaveTextContent("שיבוצים לחדרים, קריאות ותיקונים");
    expect(dialog).toHaveTextContent("בתום תקופת השמירה");
    // A return is a NEW record — re-hire continuity is OUT.
    expect(dialog).toHaveTextContent("כאשת צוות חדשה");
    // And the two IMMEDIATE facts, including the photo.
    expect(dialog).toHaveTextContent("התמונה שלה תימחק מיד");
  });

  it("refuses a last day before her start date, before any request", async () => {
    listStaff.mockResolvedValue([OWNER, member({ start_date: "2026-06-01" })]);
    renderSection();
    await screen.findByText("דנה");

    const dialog = openOffboard();
    fireEvent.change(within(dialog as HTMLElement).getByLabelText("יום עבודה אחרון"), {
      target: { value: "2026-05-31" },
    });
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "סיום העסקה" }));

    expect(await within(dialog as HTMLElement).findByRole("alert")).toHaveTextContent(
      "אינו יכול להקדים את תאריך תחילת העבודה",
    );
    expect(deactivateStaff).not.toHaveBeenCalled();
  });

  it("sends the chosen date rather than today when the owner picks one", async () => {
    listStaff.mockResolvedValue([OWNER, member({ start_date: "2020-01-01" })]);
    deactivateStaff.mockResolvedValue({ ok: true });
    renderSection();
    await screen.findByText("דנה");

    const dialog = openOffboard();
    fireEvent.change(within(dialog as HTMLElement).getByLabelText("יום עבודה אחרון"), {
      target: { value: "2026-08-31" },
    });
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "סיום העסקה" }));

    await waitFor(() => expect(deactivateStaff).toHaveBeenCalledWith(HER, "2026-08-31"));
  });

  it("names her and the date in the one status line, with the name isolated", async () => {
    // The row leaves the list, so this is the ONLY feedback there is — which is
    // exactly why it exists. F51 showed nothing here, and F51's act had no
    // retention consequence worth stating.
    listStaff.mockResolvedValue([OWNER, member({ display_name: "dana (bella)." })]);
    deactivateStaff.mockResolvedValue({ ok: true });
    renderSection();
    await screen.findByText("dana (bella).");

    fireEvent.click(
      within(rowFor("dana (bella).")).getByRole("button", { name: /^סיום העסקה/ }),
    );
    const dialog = screen.getByRole("dialog", { hidden: true });
    fireEvent.click(within(dialog as HTMLElement).getByRole("button", { name: "סיום העסקה" }));

    const status = await waitFor(() => {
      const node = screen.getByRole("status");
      expect(node).toHaveTextContent("רישומי העבודה שלה נשמרו");
      return node;
    });
    const isolated = within(status).getByText("dana (bella).");
    expect(isolated.tagName).toBe("BDI");
    expect(isolated).not.toHaveAttribute("dir");
  });
});

// --- accessibility on F38's new states: IS 5568 / WCAG 2.0 AA is legal ---

describe("StaffSection accessibility with F38's surface", () => {
  it("passes axe with photos on the list", async () => {
    listStaff.mockResolvedValue([
      OWNER,
      member({ photo_url: "https://bucket.example/k?sig", photo_confirmed_at: "2026-08-01T09:00:00Z" }),
    ]);
    const { container } = renderSection();
    await screen.findByText("דנה");
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("passes axe with the edit panel open mid-upload", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    // Never settles: the panel is scanned while the input is disabled and the
    // role="status" region carries «מעלה…».
    staffPhotoPresign.mockReturnValue(new Promise(() => {}));
    const { container } = renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");
    pick(row, "תמונת פרופיל", imageFile());

    await screen.findByText("מעלה…");
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("passes axe with the offboard dialog open", async () => {
    listStaff.mockResolvedValue([OWNER, member()]);
    const { container } = renderSection();
    await screen.findByText("דנה");
    fireEvent.click(within(rowFor("דנה")).getByRole("button", { name: /^סיום העסקה/ }));
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("passes axe with the remove-photo dialog open", async () => {
    listStaff.mockResolvedValue([
      OWNER,
      member({ photo_url: "https://bucket.example/k?sig", photo_confirmed_at: "2026-08-01T09:00:00Z" }),
    ]);
    const { container } = renderSection();
    await screen.findByText("דנה");
    const row = editorFor("דנה");
    fireEvent.click(within(row).getByRole("button", { name: "הסרת תמונה" }));
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("gives every photo an empty alt and every initial fallback aria-hidden", async () => {
    // The display name is a text node immediately beside the image, so
    // `alt="תמונה של {{name}}"` would announce her name twice per row. The photo
    // is the definition of decorative here.
    listStaff.mockResolvedValue([
      OWNER,
      member({ photo_url: "https://bucket.example/k?sig", photo_confirmed_at: "2026-08-01T09:00:00Z" }),
    ]);
    const { container } = renderSection();
    await screen.findByText("דנה");

    for (const image of container.querySelectorAll("img")) {
      expect(image.getAttribute("alt")).toBe("");
    }
    // שרה has no photo, so her cell is the initial fallback.
    const fallback = within(rowFor("שרה")).getByText("ש");
    expect(fallback).toHaveAttribute("aria-hidden", "true");
  });
});
