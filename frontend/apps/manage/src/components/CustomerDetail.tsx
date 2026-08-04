import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Badge,
  Button,
  Card,
  cn,
  focusRing,
  Input,
  Skeleton,
  TextArea,
  useToast,
} from "@boutique/ui";
import type { BadgeVariant } from "@boutique/ui";
import { api } from "../api";
import type { CustomerDetailResponse, UpdateCustomerRequest } from "../api";
import { customerErrorText, statusBadge } from "../lib/booking";
import { jerusalemDate, jerusalemTime } from "../lib/jerusalem";
import {
  MAX_CUSTOMER_NOTES_LENGTH,
  MAX_TAG_LENGTH,
  MAX_TAGS,
  validateCustomerNotes,
  validateTag,
} from "../validation";

export interface CustomerDetailProps {
  customerId: string;
  onBack: () => void;
  onCustomerChanged: (detail: CustomerDetailResponse) => void;
}

// The raw enum values off MessageKind / MessageStatus. An unknown one renders
// its RAW value rather than an empty cell — the statusBadge shape — because a
// backend that grew a sixth kind must not blank a row in an evidence log.
const MESSAGE_KIND_KEYS = new Map<string, string>([
  ["otp", "customers.messageKindOtp"],
  ["confirmation", "customers.messageKindConfirmation"],
  ["reminder", "customers.messageKindReminder"],
  ["owner_cancel", "customers.messageKindOwnerCancel"],
  ["owner_reschedule", "customers.messageKindOwnerReschedule"],
]);

// Colour never carries the state alone: the Hebrew word is inside the Badge and
// the variant is redundant reinforcement. `danger` is right here and wrong for a
// cancelled booking — a failed send is something the owner can act on.
const MESSAGE_STATUS = new Map<string, { variant: BadgeVariant; labelKey: string }>([
  ["queued", { variant: "muted", labelKey: "customers.messageStatusQueued" }],
  ["sent", { variant: "neutral", labelKey: "customers.messageStatusSent" }],
  ["failed", { variant: "danger", labelKey: "customers.messageStatusFailed" }],
]);

function messageStatusBadge(status: string): { variant: BadgeVariant; labelKey: string } {
  return MESSAGE_STATUS.get(status) ?? { variant: "neutral", labelKey: status };
}

// Mirrors BOOKING_HISTORY_LIMIT. NOT parity-guarded, and deliberately so: it
// drives one sentence under a list the server has already truncated, so a drift
// shows the notice at the wrong count rather than showing wrong rows. The four
// bounds that gate a WRITE do ride the mirror.
const BOOKING_HISTORY_LIMIT = 50;

// Local and un-exported, NOT imported from BookingDetail: CustomersSection
// imports this file, so reaching into BookingDetail would close the list→detail
// chain into a cycle.
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col md:grid md:grid-cols-[max-content_1fr] md:gap-x-4">
      <span className="text-sm text-ink-muted">{label}</span>
      <span className="text-base text-ink">{children}</span>
    </div>
  );
}

// d.m.yyyy · HH:MM, both Jerusalem, one <bdi dir="ltr"> per numeric run.
function Instant({ value }: { value: string }) {
  return (
    <>
      <bdi dir="ltr">{jerusalemDate(value)}</bdi> · <bdi dir="ltr">{jerusalemTime(value)}</bdi>
    </>
  );
}

function sameTags(draft: string[], saved: string[]): boolean {
  return draft.length === saved.length && draft.every((tag, index) => tag === saved[index]);
}

export function CustomerDetail({ customerId, onBack, onCustomerChanged }: CustomerDetailProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const [detail, setDetail] = useState<CustomerDetailResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notesDraft, setNotesDraft] = useState("");
  const [tagsDraft, setTagsDraft] = useState<string[]>([]);
  const [tagDraft, setTagDraft] = useState("");
  // Two field errors, not one: the notes message belongs in the TextArea's own
  // error slot and the tag message in the Input's, and a single string cannot
  // say which control it is about.
  const [notesError, setNotesError] = useState<string | null>(null);
  const [tagError, setTagError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // F20 / §30A. Its own error slot, not `saveError`: the withdrawal is a
  // different action on a different route, and a failed revocation announced in
  // the notes form's alert would read as "your notes did not save".
  const [consentError, setConsentError] = useState<string | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);

  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const saveAlertRef = useRef<HTMLParagraphElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getCustomer(customerId)
      .then((loaded) => {
        if (!cancelled) {
          setDetail(loaded);
          setNotesDraft(loaded.notes ?? "");
          setTagsDraft(loaded.tags);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(customerErrorText(error, t, "customers.detailFailed"));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [customerId, t]);

  // The owner hears where she landed when a row opens the detail.
  useEffect(() => {
    headingRef.current?.focus();
  }, [customerId]);

  // tabIndex={-1} on the alert is what makes this work at all: a <p> is not
  // focusable, so .focus() on a plain paragraph is a silent no-op that leaves
  // focus on the re-enabled Save button or drops it to <body> — a bug axe
  // cannot see, and one this console has already shipped and fixed.
  useEffect(() => {
    if (saveError !== null) {
      saveAlertRef.current?.focus();
    }
  }, [saveError]);

  const loading = detail === null && loadError === null;

  const addTag = () => {
    const trimmed = tagDraft.trim();
    if (trimmed === "") {
      // Typing nothing and pressing «הוספה» is not a mistake worth a sentence,
      // and the server drops a whitespace-only tag silently for the same reason.
      return;
    }
    const invalid = validateTag(trimmed, tagsDraft);
    if (invalid !== null) {
      setTagError(t(invalid, { length: MAX_TAG_LENGTH, max: MAX_TAGS }));
      return;
    }
    // Appended to the END: caller order is preserved server-side, so where she
    // put it is where it stays.
    setTagsDraft([...tagsDraft, trimmed]);
    setTagDraft("");
    setTagError(null);
  };

  const handleSave = async () => {
    if (detail === null) {
      return;
    }
    // Validate FIRST. maxLength on a <textarea> bounds length but does not
    // filter control characters, so a note pasted out of Word carrying U+000B
    // would reach the server, raise CustomerValidationError, and render its
    // ENGLISH message into a Hebrew console.
    const invalid = validateCustomerNotes(notesDraft);
    if (invalid !== null) {
      setNotesError(t(invalid, { length: MAX_CUSTOMER_NOTES_LENGTH }));
      return;
    }
    setNotesError(null);
    // Only what actually moved. An all-unchanged patch is a no-op the server
    // answers 200 without writing an audit row, so sending less is not an
    // optimisation — it is what keeps the audit table meaningful.
    const body: UpdateCustomerRequest = {};
    if (notesDraft !== (detail.notes ?? "")) {
      body.notes = notesDraft;
    }
    if (!sameTags(tagsDraft, detail.tags)) {
      body.tags = tagsDraft;
    }
    if (Object.keys(body).length === 0) {
      return;
    }
    setSaving(true);
    try {
      const updated = await api.updateCustomer(detail.id, body);
      setDetail(updated);
      // Re-seeded from the RESPONSE, never kept: the server normalizes tags, so
      // the chips can legitimately come back deduped and re-cased.
      setNotesDraft(updated.notes ?? "");
      setTagsDraft(updated.tags);
      setTagDraft("");
      setTagError(null);
      setSaveError(null);
      onCustomerChanged(updated);
      toast({ message: t("customers.saved") });
    } catch (error) {
      // The fallback key is not optional here. Without it every code outside
      // {NOT_FOUND, NOT_AUTHORIZED} renders the server's ENGLISH message into a
      // Hebrew RTL console — and the focus move below lands on that alert. The
      // concrete one is a 401 NOT_AUTHENTICATED when her session expires with
      // the card open.
      setSaveError(customerErrorText(error, t, "customers.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  // ⚠ THREE STATES, NOT A BOOLEAN. Effective consent is
  // `marketing_consent_at IS NOT NULL AND marketing_consent_withdrawn_at IS
  // NULL`; withdrawal is ADDITIVE because clearing the grant timestamp would
  // destroy the Spam-Law evidence that the consent existed when a message was
  // sent. So «הוסרה» is a real third state and not the absence of the first, and
  // collapsing the two would tell a staffer a woman never consented when the
  // record says she did and then revoked.
  const consentKey =
    detail === null || detail.marketing_consent_at === null
      ? "privacy.consentNone"
      : detail.marketing_consent_withdrawn_at === null
        ? "privacy.consentActive"
        : "privacy.consentWithdrawn";
  const consentLive = consentKey === "privacy.consentActive";

  const handleWithdraw = async () => {
    if (detail === null) return;
    setWithdrawing(true);
    setConsentError(null);
    try {
      await api.withdrawMarketingConsent({ customer_id: detail.id });
      // Patched locally rather than refetched. The response is one boolean, and
      // re-reading the whole card to learn what we just did would blank the
      // booking history and the message log for the length of a round trip.
      // Written only AFTER the call resolves — an optimistic flip would tell a
      // staffer she had honoured a §30A revocation that never landed.
      setDetail({ ...detail, marketing_consent_withdrawn_at: new Date().toISOString() });
    } catch {
      setConsentError(t("privacy.withdrawFailed"));
    } finally {
      setWithdrawing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* First in reading order, and rendered unconditionally: without it a
          failed load has no way out. size="md" deliberately — size="sm"'s
          min-h-9 is under the 44px floor. */}
      <Button variant="ghost" size="md" onClick={onBack}>
        {t("customers.back")}
      </Button>

      {/* The name IS the heading here, unlike BookingDetail: this screen is
          about a person and the console is behind a role gate. Bare bdi —
          dir="ltr" on a Hebrew name is itself a bidi defect. */}
      <h2 ref={headingRef} tabIndex={-1} className="font-display text-xl text-ink">
        <bdi>{detail?.name ?? ""}</bdi>
      </h2>

      {/* The detail view's ONE announced region. */}
      <p role="status" tabIndex={-1} className="text-sm text-ink-muted">
        {loading ? t("customers.detailLoading") : ""}
      </p>

      {loadError !== null && (
        // An outage or a card that is gone, neither of them her fault: the muted
        // register, and no retry control.
        <p role="alert" className="text-sm text-ink-muted">
          {loadError}
        </p>
      )}

      {/* variant="text", never the default "block" — that one renders
          h-full w-full and collapses to zero height in a parent with no
          intrinsic height. */}
      {loading && <Skeleton variant="text" lines={6} />}

      {detail !== null && (
        <>
          <Card className="space-y-3">
            <Fact label={t("customers.phoneLabel")}>
              <bdi dir="ltr">{detail.phone}</bdi>
            </Fact>
            {/* ⚠ F20 / Gate 1 Q4, AND THIS IS WHERE THAT RULING BECOMES
                REACHABLE. The privacy section is owner-only because its first
                step is the §13 export; `POST /manage/privacy/marketing-withdraw`
                deliberately carries NO route-level gate and inherits the
                router's (OWNER, SHIFT_MANAGER) one. A shift manager taking the
                call has to be able to honour «אפשר לבקש מאיתנו להסיר את ההסכמה
                בכל עת» from the screen she is already on — and looking a caller
                up is what this card is for.

                No role prop and no client-side filter: the server admits both
                console roles, so a filter here would be this component lying
                about the API rather than mirroring it. */}
            <Fact label={t("privacy.consentLabel")}>
              {/* The WORD carries the state and the variant is redundant
                  reinforcement — colour is never the sole indicator. */}
              <Badge
                data-testid="customer-consent"
                variant={consentLive ? "neutral" : "muted"}
              >
                {t(consentKey)}
              </Badge>
            </Fact>
            {consentLive && (
              // Rendered ONLY where there is a live consent to withdraw: a
              // control that answers `changed: false` is a control that did
              // nothing, and offering it on a card with no consent invites a
              // staffer to "do it again" on a subject who never gave one.
              //
              // No confirmation step, and that is §30A rather than an oversight:
              // revocation may not be conditioned, and a modal asking «are you
              // sure?» at the counter is a condition however small.
              <Button
                variant="secondary"
                size="md"
                loading={withdrawing}
                onClick={() => void handleWithdraw()}
              >
                {t("privacy.withdraw")}
              </Button>
            )}
            {consentError !== null && (
              <p role="alert" className="text-sm text-danger">
                {consentError}
              </p>
            )}
          </Card>

          <Card className="space-y-4">
            <TextArea
              label={t("customers.notesLabel")}
              help={t("customers.notesHelp")}
              placeholder={t("customers.notesPlaceholder")}
              showCount
              maxLength={MAX_CUSTOMER_NOTES_LENGTH}
              rows={5}
              value={notesDraft}
              error={notesError ?? undefined}
              onChange={(event) => {
                setNotesDraft(event.target.value);
                setNotesError(null);
              }}
            />

            <div className="space-y-2">
              <p className="text-sm font-semibold text-ink">{t("customers.tagsLabel")}</p>
              {tagsDraft.length === 0 ? (
                <p className="text-sm text-ink-muted">{t("customers.tagsEmpty")}</p>
              ) : (
                <div data-testid="customer-tags" className="flex flex-wrap gap-2">
                  {tagsDraft.map((tag) => (
                    <Badge key={tag} variant="neutral" className="gap-2">
                      <bdi>{tag}</bdi>
                      <button
                        type="button"
                        // The accessible name STARTS with the visible label —
                        // WCAG 2.5.3, so speech input can say what it reads.
                        aria-label={t("customers.tagRemoveAria", { tag })}
                        className={cn("rounded-full px-1 py-1 text-ink-muted", focusRing)}
                        onClick={() => {
                          setTagsDraft(tagsDraft.filter((current) => current !== tag));
                          setTagError(null);
                        }}
                      >
                        {t("customers.tagRemove")}
                      </button>
                    </Badge>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-end gap-3">
                <Input
                  label={t("customers.tagAddLabel")}
                  help={t("customers.tagsHelp", { max: MAX_TAGS, length: MAX_TAG_LENGTH })}
                  className="max-w-[240px]"
                  maxLength={MAX_TAG_LENGTH}
                  value={tagDraft}
                  error={tagError ?? undefined}
                  onChange={(event) => {
                    setTagDraft(event.target.value);
                    setTagError(null);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      // A bare Enter in a text field would submit an enclosing
                      // form; there is none here, but the intent is "add", not
                      // "save".
                      event.preventDefault();
                      addTag();
                    }
                  }}
                />
                <Button variant="secondary" size="md" onClick={addTag}>
                  {t("customers.tagAdd")}
                </Button>
              </div>
            </div>

            {saveError !== null && (
              // The fix-this register, not the outage one: a rejected save is
              // something she can correct.
              <p
                role="alert"
                tabIndex={-1}
                ref={saveAlertRef}
                data-testid="customer-save-error"
                className="text-sm text-danger"
              >
                {saveError}
              </p>
            )}

            <Button onClick={handleSave} loading={saving}>
              {t("customers.save")}
            </Button>
          </Card>

          <Card className="space-y-3">
            <h3 className="text-base font-semibold text-ink">{t("customers.bookingsHeading")}</h3>
            {detail.bookings.length === 0 ? (
              <p className="text-sm text-ink-muted">{t("customers.bookingsEmpty")}</p>
            ) : (
              <ul className="divide-y divide-border">
                {detail.bookings.map((booking) => {
                  const badge = statusBadge(booking.status);
                  return (
                    <li key={booking.id} className="flex flex-wrap items-center gap-3 py-3">
                      <span className="text-sm text-ink">
                        <Instant value={booking.starts_at} />
                      </span>
                      <span className="min-w-0 grow text-sm text-ink-muted">
                        <bdi>{booking.appointment_type_name}</bdi>
                      </span>
                      <Badge variant={badge.variant}>{t(badge.labelKey)}</Badge>
                    </li>
                  );
                })}
              </ul>
            )}
            {detail.bookings.length >= BOOKING_HISTORY_LIMIT && (
              <p className="text-sm text-ink-muted">
                {t("customers.bookingsTruncated", { count: detail.bookings.length })}
              </p>
            )}
          </Card>

          <Card className="space-y-3">
            {/* «יומן הודעות», never «הודעות שנשלחו»: the rows below include
                status = 'failed', so a heading claiming they were sent would be
                a lie about the table under it. */}
            <h3 className="text-base font-semibold text-ink">{t("customers.messagesHeading")}</h3>
            <p className="text-sm text-ink-muted">{t("customers.messagesHelp")}</p>
            {detail.messages.length === 0 ? (
              <p className="text-sm text-ink-muted">{t("customers.messagesEmpty")}</p>
            ) : (
              <>
                {/* No control of ANY kind on a log row — no resend, no delete,
                    no expand. A mutable evidence trail is not evidence. */}
                <ul className="divide-y divide-border">
                  {detail.messages.map((message) => {
                    const badge = messageStatusBadge(message.status);
                    const kindKey = MESSAGE_KIND_KEYS.get(message.kind) ?? message.kind;
                    return (
                      <li key={message.id} className="space-y-1 py-3">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-sm text-ink-muted">
                            <Instant value={message.created_at} />
                          </span>
                          <span className="text-sm text-ink">
                            {t(kindKey)}
                          </span>
                          {/* An unknown status falls back to labelKey = the raw
                              value, and i18next renders a missing key as
                              itself — so a sixth status reads as its own name
                              rather than as an empty chip. */}
                          <Badge variant={badge.variant}>{t(badge.labelKey)}</Badge>
                        </span>
                        <p className="text-sm text-ink">
                          <bdi>{message.body}</bdi>
                        </p>
                      </li>
                    );
                  })}
                </ul>
                {detail.messages_total > detail.messages.length && (
                  // Both numbers, so the send volume stays readable even when
                  // the fifty-row window truncated. Mid-sentence with Hebrew on
                  // both sides, so neither needs isolating.
                  <p className="text-sm text-ink-muted">
                    {t("customers.messagesTruncated", {
                      count: detail.messages.length,
                      total: detail.messages_total,
                    })}
                  </p>
                )}
              </>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
