import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import i18n from "../i18n";
import type { PrivacyResponse, SubjectExportResponse } from "../api";
import { PrivacySection } from "../components/PrivacySection";
import { MAX_PRIVACY_TEXT_BYTES } from "../validation";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      getPrivacy: vi.fn(),
      updatePrivacy: vi.fn(),
      exportSubject: vi.fn(),
      eraseSubject: vi.fn(),
      withdrawMarketingConsent: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const getPrivacy = vi.mocked(api.getPrivacy);
const updatePrivacy = vi.mocked(api.updatePrivacy);
const exportSubject = vi.mocked(api.exportSubject);
const eraseSubject = vi.mocked(api.eraseSubject);
const withdrawMarketingConsent = vi.mocked(api.withdrawMarketingConsent);

const CUSTOMER_ID = "11111111-2222-3333-4444-555555555555";
const PHONE = "+972501234567";

// Short stand-ins, deliberately NOT the approved legal Hebrew: that text lives in
// `app/privacy/text.py` and a copy here would be a second place for it to drift
// — the exact thing `i18n.test.ts`'s "holds NO copy" assertion forbids one file
// over. What matters to these tests is that whatever the API sends is what the
// console shows and sends back.
function privacy(overrides: Partial<PrivacyResponse> = {}): PrivacyResponse {
  return {
    notice_text: "נוסח ברירת המחדל של ההודעה.",
    notice_is_default: true,
    dpa_text: "נוסח ברירת המחדל של סעיף העיבוד.",
    dpa_is_default: true,
    subprocessors_text: "רשימת הספקים.",
    disclaimer_text: "אזהרה שהנוסח לא נבדק על ידי עורך דין.",
    erase_reason_hint: "לרשום למה נמחק המידע ולא את מי.",
    ...overrides,
  };
}

function exported(overrides: Partial<SubjectExportResponse["subject"]> = {}): SubjectExportResponse {
  return {
    subject: {
      id: CUSTOMER_ID,
      phone: PHONE,
      name: "מיכל לוי",
      created_at: "2026-01-04T07:00:00Z",
      notes: null,
      tags: [],
      marketing_consent_at: null,
      marketing_consent_source: null,
      marketing_consent_withdrawn_at: null,
      erased_at: null,
      ...overrides,
    },
    bookings: [],
    messages: [],
    queue_tickets: [],
    accepted_terms: [],
  };
}

// PrivacySection renders inside ConsoleShell's <main>, which owns the console's
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

async function open(response: PrivacyResponse = privacy()) {
  getPrivacy.mockResolvedValue(response);
  const utils = renderInShell(<PrivacySection />);
  await screen.findByLabelText(i18n.t("privacy.noticeLabel"));
  return utils;
}

function noticeField(): HTMLTextAreaElement {
  return screen.getByLabelText(i18n.t("privacy.noticeLabel"));
}

function dpaField(): HTMLTextAreaElement {
  return screen.getByLabelText(i18n.t("privacy.dpaLabel"));
}

function saveButton(): HTMLElement {
  return screen.getByRole("button", { name: i18n.t("privacy.save") });
}

async function lookup() {
  fireEvent.change(screen.getByLabelText(i18n.t("privacy.phoneLabel")), {
    target: { value: "0501234567" },
  });
  fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.lookup") }));
  await screen.findByText("מיכל לוי");
}

beforeEach(() => {
  vi.clearAllMocks();
  exportSubject.mockResolvedValue(exported());
  updatePrivacy.mockImplementation((body) =>
    Promise.resolve(
      privacy({
        notice_text: body.notice_text ?? "נוסח ברירת המחדל של ההודעה.",
        notice_is_default: body.notice_text === null,
        dpa_text: body.dpa_text ?? "נוסח ברירת המחדל של סעיף העיבוד.",
        dpa_is_default: body.dpa_text === null,
      }),
    ),
  );
});

// --- the two editable documents ---------------------------------------------

describe("PrivacySection documents", () => {
  it("renders the not-lawyer-reviewed disclaimer above both fields", async () => {
    // ⚠ FROM THE API, never from `he.ts`. The disclaimer is approved legal
    // Hebrew and `PrivacyResponse` carries it for the same reason the three
    // public documents ride the storefront fetch: one copy of each string.
    await open();

    const disclaimer = screen.getByText("אזהרה שהנוסח לא נבדק על ידי עורך דין.");
    expect(disclaimer).toBeInTheDocument();
    // Above both, in DOM order — the warning is worthless underneath the boxes
    // it is about.
    expect(disclaimer.compareDocumentPosition(noticeField())).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("shows a per-field badge saying whether the wording is the platform's", async () => {
    await open(privacy({ dpa_text: "הנוסח שלנו.", dpa_is_default: false }));

    expect(screen.getByTestId("privacy-notice-badge")).toHaveTextContent(
      i18n.t("privacy.isDefault"),
    );
    // Independently: the two documents are overridden separately, so one badge
    // for the pair would be wrong half the time.
    expect(screen.getByTestId("privacy-dpa-badge")).toHaveTextContent(i18n.t("privacy.isCustom"));
  });

  it("counts BYTES against the server's cap, not characters", async () => {
    // Hebrew is two bytes per character in UTF-8, so a character counter would
    // tell an owner she has 8 000 left when the server refuses her at 4 096.
    await open();
    fireEvent.change(noticeField(), { target: { value: "אב" } });

    expect(
      screen.getByText(i18n.t("privacy.bytes", { used: 4, max: MAX_PRIVACY_TEXT_BYTES })),
    ).toBeInTheDocument();
  });

  it("refuses to send a document over the cap, and says so", async () => {
    await open();
    fireEvent.change(noticeField(), { target: { value: "א".repeat(MAX_PRIVACY_TEXT_BYTES) } });

    fireEvent.click(saveButton());

    expect(await screen.findByText(i18n.t("privacy.tooLong"))).toBeInTheDocument();
    expect(updatePrivacy).not.toHaveBeenCalled();
  });

  it("submits BOTH fields even when only one was edited", async () => {
    // ⚠ D16, AND THE REASON IS NOT STYLE. `merge_settings` is one
    // `settings = settings || :patch::jsonb` and `||` replaces WHOLE top-level
    // keys — a patch naming only `notice_text` replaces the entire `privacy`
    // object, and the server then reads the absent `dpa_text` as "use the
    // platform default". An owner who overrode her processor clause on Monday
    // and edits only her notice on Tuesday would silently lose Monday's work.
    await open(
      privacy({
        notice_text: "נוסח משלה.",
        notice_is_default: false,
        dpa_text: "סעיף משלה.",
        dpa_is_default: false,
      }),
    );
    fireEvent.change(noticeField(), { target: { value: "נוסח חדש." } });

    fireEvent.click(saveButton());

    await waitFor(() => {
      expect(updatePrivacy).toHaveBeenCalledWith({
        notice_text: "נוסח חדש.",
        dpa_text: "סעיף משלה.",
      });
    });
  });

  it("sends null for a field still on the platform wording, so a platform amendment still reaches her", async () => {
    // The other half of the always-send-both rule. Sending the RESOLVED text
    // back for an untouched default would turn it into an override with
    // identical words — and the boutique would silently stop receiving platform
    // corrections to a legal document she never chose to own.
    await open();
    fireEvent.change(dpaField(), { target: { value: "סעיף חדש." } });

    fireEvent.click(saveButton());

    await waitFor(() => {
      expect(updatePrivacy).toHaveBeenCalledWith({
        notice_text: null,
        dpa_text: "סעיף חדש.",
      });
    });
  });

  it("reverts one field by submitting an empty string, and leaves the other alone", async () => {
    await open(
      privacy({
        notice_text: "נוסח משלה.",
        notice_is_default: false,
        dpa_text: "סעיף משלה.",
        dpa_is_default: false,
      }),
    );

    // BY ITS ARIA NAME, and that is the assertion as much as the click: with
    // both documents overridden there are TWO revert controls whose visible text
    // is identical, so a name-blind query is ambiguous — which is exactly what a
    // speech-input user hits. WCAG 2.5.3 holds because the accessible name
    // STARTS with the visible label.
    fireEvent.click(
      screen.getByRole("button", {
        name: i18n.t("privacy.revertAria", { document: i18n.t("privacy.noticeLabel") }),
      }),
    );

    await waitFor(() => {
      // `""` and not `null`: `merge_settings` can add or replace a JSONB key but
      // never remove one, so the empty string is the only revert sentinel an
      // owner can actually reach — and the server collapses it to the default.
      expect(updatePrivacy).toHaveBeenCalledWith({ notice_text: "", dpa_text: "סעיף משלה." });
    });
  });

  it("renders the sub-processor list with no control of any kind", async () => {
    // Gate 1 Q3 / D14 from the owner's side. The list is platform-owned so that
    // one amendment reaches every tenant structurally; the ABSENCE of a control
    // is the disclosure, and the disclaimer above says in words why the box is
    // missing so nobody has to guess.
    await open();

    const block = screen.getByTestId("privacy-subprocessors");
    expect(block).toHaveTextContent("רשימת הספקים.");
    expect(within(block).queryAllByRole("textbox")).toEqual([]);
    expect(within(block).queryAllByRole("button")).toEqual([]);
  });

  it("passes axe with zero violations", async () => {
    const { container } = await open();

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);
});

// --- the subject-request panel ----------------------------------------------

describe("PrivacySection subject requests", () => {
  it("keeps erase and withdraw disabled until a lookup resolved a customer id", async () => {
    // ⚠ D17's ORDER, made structural. Both routes are keyed on `customer_id`
    // and the §13 export is the ONLY place that id comes from — step 2 of the
    // erase overwrites `customers.phone`, so a phone-keyed erase would destroy
    // its own lookup key.
    await open();

    expect(screen.getByRole("button", { name: i18n.t("privacy.erase") })).toBeDisabled();
    expect(screen.getByRole("button", { name: i18n.t("privacy.withdraw") })).toBeDisabled();

    await lookup();

    expect(screen.getByRole("button", { name: i18n.t("privacy.erase") })).toBeEnabled();
    expect(screen.getByRole("button", { name: i18n.t("privacy.withdraw") })).toBeEnabled();
  });

  it("says plainly that no customer has that number", async () => {
    exportSubject.mockRejectedValue(new ApiError(404, "SUBJECT_NOT_FOUND", "not found"));
    await open();

    fireEvent.change(screen.getByLabelText(i18n.t("privacy.phoneLabel")), {
      target: { value: "0501234567" },
    });
    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.lookup") }));

    expect(await screen.findByText(i18n.t("privacy.notFound"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: i18n.t("privacy.erase") })).toBeDisabled();
  });

  it("hangs the reason hint off the API, never off he.ts", async () => {
    await open();
    await lookup();

    expect(screen.getByLabelText(i18n.t("privacy.reasonLabel"))).toHaveAccessibleDescription(
      new RegExp("לרשום למה נמחק המידע ולא את מי"),
    );
  });

  it("cannot erase on one click", async () => {
    await open();
    await lookup();

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.erase") }));

    expect(eraseSubject).not.toHaveBeenCalled();
    expect(screen.getByLabelText(i18n.t("privacy.eraseConfirmLabel"))).toBeInTheDocument();
  });

  it("requires the subject's own phone digits re-typed, and refuses a near miss", async () => {
    // ⚠ HER DIGITS AND NOT A FIXED WORD, and every part of that is deliberate.
    // An ASCII LTR run has no bidi ambiguity in an RTL field, which a Hebrew
    // «מחק» would; it is already on screen, so this is a transcription rather
    // than a memory test; and it is DIFFERENT FOR EVERY SUBJECT, so it cannot be
    // satisfied by the muscle memory one fixed word builds after three uses.
    await open();
    await lookup();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.erase") }));

    fireEvent.change(screen.getByLabelText(i18n.t("privacy.eraseConfirmLabel")), {
      target: { value: "+97250123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.eraseConfirmCta") }));

    expect(await screen.findByText(i18n.t("privacy.eraseConfirmMismatch"))).toBeInTheDocument();
    expect(eraseSubject).not.toHaveBeenCalled();
  });

  // The walkthrough's finding: the confirm compared the typed string to the
  // stored E.164 EXACTLY, so `0501234599` — the format the lookup field's own
  // help text tells her to use, and the format she just used to FIND this
  // customer — was refused with «המספר שהוקלד אינו תואם». On an irreversible
  // privacy action, "the number you typed doesn't match" invites the operator to
  // conclude she has the wrong woman, and the next move after that conclusion is
  // to go looking for a different customer to erase.
  it("accepts the LOCAL format its own lookup accepted, not only the stored E.164", async () => {
    eraseSubject.mockResolvedValue({
      customer_id: CUSTOMER_ID,
      already_erased: false,
      bookings_scrubbed: 0,
      messages_scrubbed: 0,
      queue_tickets_scrubbed: 0,
      otp_codes_purged: 0,
      scheduled_messages_purged: 0,
    });
    await open();
    await lookup();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.erase") }));
    // PHONE is "+972501234567"; this is the same number as she would dial it.
    fireEvent.change(screen.getByLabelText(i18n.t("privacy.eraseConfirmLabel")), {
      target: { value: "050-123-4567" },
    });

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.eraseConfirmCta") }));

    await waitFor(() => {
      expect(eraseSubject).toHaveBeenCalledWith({ customer_id: CUSTOMER_ID, reason: null });
    });
    expect(screen.queryByText(i18n.t("privacy.eraseConfirmMismatch"))).toBeNull();
  });

  it("refuses a BLANK confirmation even against a subject whose phone carries no digits", async () => {
    // The one way a looser comparison could go wrong, and the reason `erase()`
    // guards `typed === ""` separately: two empty normalisations are equal.
    //
    // ⚠ The digitless phone is what makes this test able to FAIL. Against an
    // ordinary `+9725…` subject a blank field is refused by the comparison alone,
    // so removing the guard reds nothing and the guard would be a line no
    // mutation could reach. `by_phone` is exact equality on normalised E.164, so
    // the server cannot produce this row today — the guard is defence for an
    // irreversible action, and this is the assertion that keeps it honest.
    exportSubject.mockResolvedValue(exported({ phone: "" }));
    await open();
    await lookup();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.erase") }));

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.eraseConfirmCta") }));

    expect(await screen.findByText(i18n.t("privacy.eraseConfirmMismatch"))).toBeInTheDocument();
    expect(eraseSubject).not.toHaveBeenCalled();
  });

  it("erases on the matching phone, keyed on the id the lookup returned", async () => {
    eraseSubject.mockResolvedValue({
      customer_id: CUSTOMER_ID,
      already_erased: false,
      bookings_scrubbed: 2,
      messages_scrubbed: 4,
      queue_tickets_scrubbed: 1,
      otp_codes_purged: 1,
      scheduled_messages_purged: 0,
    });
    await open();
    await lookup();
    fireEvent.change(screen.getByLabelText(i18n.t("privacy.reasonLabel")), {
      target: { value: "בקשה טלפונית שאומתה" },
    });
    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.erase") }));
    fireEvent.change(screen.getByLabelText(i18n.t("privacy.eraseConfirmLabel")), {
      target: { value: PHONE },
    });

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.eraseConfirmCta") }));

    await waitFor(() => {
      expect(eraseSubject).toHaveBeenCalledWith({
        customer_id: CUSTOMER_ID,
        reason: "בקשה טלפונית שאומתה",
      });
    });
  });

  it("renders the 409 in Hebrew rather than the server's English", async () => {
    eraseSubject.mockRejectedValue(
      new ApiError(409, "SUBJECT_HAS_ACTIVE_BOOKING", "Customer has a confirmed future booking."),
    );
    await open();
    await lookup();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.erase") }));
    fireEvent.change(screen.getByLabelText(i18n.t("privacy.eraseConfirmLabel")), {
      target: { value: PHONE },
    });

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.eraseConfirmCta") }));

    expect(await screen.findByText(i18n.t("privacy.error.SUBJECT_HAS_ACTIVE_BOOKING"))).toBeInTheDocument();
    expect(screen.queryByText(/Customer has a confirmed/)).toBeNull();
  });

  it("withdraws the marketing consent with no confirmation step", async () => {
    // §30A says revocation may not be conditioned, and a modal asking «are you
    // sure?» at the counter is a condition however small. It is also the LESSER
    // action and reversible by asking again — unlike the erase beside it.
    withdrawMarketingConsent.mockResolvedValue({ changed: true });
    await open();
    await lookup();

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.withdraw") }));

    await waitFor(() => {
      expect(withdrawMarketingConsent).toHaveBeenCalledWith({ customer_id: CUSTOMER_ID });
    });
  });

  it("says so plainly when there was no live consent to remove", async () => {
    withdrawMarketingConsent.mockResolvedValue({ changed: false });
    await open();
    await lookup();

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.withdraw") }));

    expect(await screen.findByText(i18n.t("privacy.withdrawNoop"))).toBeInTheDocument();
  });
});
