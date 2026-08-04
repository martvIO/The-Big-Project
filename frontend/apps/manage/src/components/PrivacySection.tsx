import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  Badge,
  Button,
  Card,
  Input,
  SectionHeading,
  Skeleton,
  TextArea,
  useToast,
} from "@boutique/ui";
import { ApiError, api, errorMessage } from "../api";
import type { PrivacyResponse, SubjectExportResponse } from "../api";
import { MAX_PRIVACY_TEXT_BYTES, utf8Bytes } from "../validation";

// The console's privacy surface: the two documents the boutique publishes, and
// the §13/§14 subject requests.
//
// ⚠ NONE OF THE LEGAL HEBREW IS IN `he.ts`. The notice, the processor clause,
// the sub-processor list, the not-lawyer-reviewed disclaimer and the
// `reason`-field hint all arrive on `GET /manage/privacy`. That is the same rule
// F33's `checkin.notice` comment states — no second copy may exist anywhere —
// and it matters twice here: a bundled copy of the notice would publish platform
// wording to a boutique whose own lawyer had rewritten hers, and a bundled copy
// of the sub-processor list would put the one document a tenant may NOT edit
// into a file a frontend change edits freely.
//
// ⚠ OWNER-ONLY, and the row is hidden from a shift manager in `App.tsx`'s NAV.
// The control is the server's RoleGate; the filter exists so she is not shown a
// door that answers 403. Her privacy permission is real and is exercised on the
// CUSTOMER CARD — `POST /manage/privacy/marketing-withdraw` carries no
// route-level gate and inherits the router's (OWNER, SHIFT_MANAGER) one.

// The codes this section renders its own Hebrew for. Everything else falls
// through to `errorMessage()`. Kept by hand, exactly like GatewaySection's and
// StaffSection's.
const MAPPED_CODES = new Set(["BOOKING_ACTIVE", "TOO_MANY_ATTEMPTS", "NOT_AUTHORIZED"]);

// The §13 export, as a file. A `data:` URL rather than `URL.createObjectURL`:
// the payload is one customer's record and is small, there is no object to
// revoke and therefore no leak to forget, and jsdom implements neither — so the
// alternative is a polyfill in the test setup for a line nothing else needs.
function exportHref(payload: SubjectExportResponse): string {
  return `data:application/json;charset=utf-8,${encodeURIComponent(
    JSON.stringify(payload, null, 2),
  )}`;
}

export function PrivacySection() {
  const { t } = useTranslation();
  const toast = useToast();

  const [privacy, setPrivacy] = useState<PrivacyResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [dpa, setDpa] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [phone, setPhone] = useState("");
  const [subject, setSubject] = useState<SubjectExportResponse | null>(null);
  const [reason, setReason] = useState("");
  const [subjectError, setSubjectError] = useState<string | null>(null);
  const [subjectNote, setSubjectNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Two-step reveal-then-confirm, the shipped GatewaySection idiom — and NOT a
  // <dialog>: jsdom ships none, `test/setup.ts` stubs `showModal()`, and every
  // vitest assertion about a modal's focus trap or its Esc route measures the
  // stub and cannot fail. An inline reveal is assertable here for real, and the
  // control it guards is irreversible.
  const [confirming, setConfirming] = useState(false);
  const [typedPhone, setTypedPhone] = useState("");
  const [mismatch, setMismatch] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getPrivacy()
      .then((loaded) => {
        if (!cancelled) {
          setPrivacy(loaded);
          setNotice(loaded.notice_text);
          setDpa(loaded.dpa_text);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(errorMessage(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (privacy === null) {
    if (loadError !== null) {
      return (
        <p role="alert" className="text-base text-ink-muted">
          {t("privacy.loadFailed")}
        </p>
      );
    }
    return <Skeleton variant="text" lines={6} />;
  }

  const errorText = (error: unknown): string => {
    if (error instanceof ApiError && MAPPED_CODES.has(error.code)) {
      return t(`privacy.error.${error.code}`);
    }
    return errorMessage(error);
  };

  // ⚠ BOTH KEYS, ALWAYS, and the two arms are both load-bearing.
  //
  // Sending both is D16: `merge_settings` is one `settings || :patch::jsonb` and
  // `||` replaces WHOLE top-level keys, so a patch naming one field replaces the
  // entire `privacy` object and the server reads the absent one as "use the
  // platform default" — an owner who overrode her processor clause on Monday and
  // edits only her notice on Tuesday would silently lose Monday's work.
  //
  // Sending `null` for a field that is STILL the platform wording and untouched
  // is the other half. Echoing the resolved default back would turn it into an
  // override with identical words, and the boutique would quietly stop receiving
  // platform corrections to a legal document she never chose to own.
  const payloadFor = (draft: string, isDefault: boolean, resolved: string): string | null =>
    isDefault && draft === resolved ? null : draft;

  const submit = async (noticeValue: string | null, dpaValue: string | null) => {
    setSaving(true);
    setSaved(false);
    setFormError(null);
    try {
      const updated = await api.updatePrivacy({ notice_text: noticeValue, dpa_text: dpaValue });
      setPrivacy(updated);
      // Re-seeded from the RESPONSE, never from the draft: a revert has to show
      // the platform wording coming back, which is the only feedback that the
      // empty-string sentinel did anything.
      setNotice(updated.notice_text);
      setDpa(updated.dpa_text);
      setSaved(true);
    } catch (error) {
      setFormError(errorText(error));
      toast({ message: t("privacy.saveFailed"), variant: "error" });
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // Client-side because the round trip would otherwise answer a house 400
    // carrying an ENGLISH message into a Hebrew RTL console, for an input error
    // that fails identically on every retry.
    if (
      utf8Bytes(notice) > MAX_PRIVACY_TEXT_BYTES ||
      utf8Bytes(dpa) > MAX_PRIVACY_TEXT_BYTES
    ) {
      setFormError(t("privacy.tooLong"));
      return;
    }
    await submit(
      payloadFor(notice, privacy.notice_is_default, privacy.notice_text),
      payloadFor(dpa, privacy.dpa_is_default, privacy.dpa_text),
    );
  };

  // `""` and not `null`: `merge_settings` can add or replace a JSONB key but
  // never remove one, so the empty string is the only revert sentinel an owner
  // can reach — and the server collapses blank to the platform default. The
  // sibling field is sent unchanged, by the same always-send-both rule.
  const revertNotice = () =>
    void submit("", payloadFor(dpa, privacy.dpa_is_default, privacy.dpa_text));
  const revertDpa = () =>
    void submit(payloadFor(notice, privacy.notice_is_default, privacy.notice_text), "");

  const lookup = async () => {
    setBusy(true);
    setSubjectError(null);
    setSubjectNote(null);
    setConfirming(false);
    setTypedPhone("");
    setMismatch(false);
    try {
      setSubject(await api.exportSubject(phone.trim(), reason.trim() === "" ? undefined : reason));
    } catch (error) {
      setSubject(null);
      setSubjectError(
        error instanceof ApiError && error.status === 404
          ? t("privacy.notFound")
          : errorText(error),
      );
    } finally {
      setBusy(false);
    }
  };

  const erase = async () => {
    if (subject === null) return;
    // The confirmation is HER phone digits re-typed: an ASCII LTR run with no
    // bidi ambiguity in an RTL field, already on screen so it is a transcription
    // rather than a memory test, and different for every subject so it cannot be
    // satisfied by the muscle memory one fixed word builds after three uses.
    if (typedPhone.trim() !== subject.subject.phone) {
      setMismatch(true);
      return;
    }
    setBusy(true);
    setMismatch(false);
    setSubjectError(null);
    try {
      const result = await api.eraseSubject({
        customer_id: subject.subject.id,
        reason: reason.trim() === "" ? null : reason,
      });
      setConfirming(false);
      setTypedPhone("");
      setSubjectNote(result.already_erased ? t("privacy.alreadyErased") : t("privacy.erased"));
      toast({ message: t("privacy.erased") });
    } catch (error) {
      setSubjectError(errorText(error));
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async () => {
    if (subject === null) return;
    setBusy(true);
    setSubjectError(null);
    try {
      const result = await api.withdrawMarketingConsent({ customer_id: subject.subject.id });
      setSubjectNote(result.changed ? t("privacy.withdrawn") : t("privacy.withdrawNoop"));
    } catch {
      // One message for every failure mode, deliberately: a revocation that did
      // not land is the same fact to the person on the telephone whether the
      // cause was a 503 or a dropped connection, and the codes this route can
      // answer carry nothing she could act on.
      setSubjectError(t("privacy.withdrawFailed"));
    } finally {
      setBusy(false);
    }
  };

  const documentField = (
    testId: string,
    labelKey: string,
    value: string,
    onChange: (next: string) => void,
    isDefault: boolean,
    onRevert: () => void,
  ) => (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <Badge data-testid={`${testId}-badge`} variant={isDefault ? "muted" : "neutral"}>
          {isDefault ? t("privacy.isDefault") : t("privacy.isCustom")}
        </Badge>
        {!isDefault && (
          <Button
            variant="ghost"
            size="md"
            // ⚠ WCAG 2.5.3 — the accessible name STARTS with the visible label,
            // so speech input can say what it reads. Two revert controls on one
            // screen have to be distinguishable by name, which is why the aria
            // form exists at all.
            aria-label={t("privacy.revertAria", { document: t(labelKey) })}
            onClick={onRevert}
          >
            {t("privacy.revert")}
          </Button>
        )}
      </div>
      <TextArea
        label={t(labelKey)}
        rows={10}
        dir="auto"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          setSaved(false);
          setFormError(null);
        }}
        className="[resize:block]"
      />
      {/* BYTES, not characters: the server's cap is measured on the UTF-8
          encoding and Hebrew is two bytes per character, so `TextArea`'s own
          `showCount` — which counts characters — would tell her she has 8 000
          left when the API refuses her at 4 096. */}
      <p className="text-xs text-ink-muted">
        {t("privacy.bytes", { used: utf8Bytes(value), max: MAX_PRIVACY_TEXT_BYTES })}
      </p>
    </div>
  );

  return (
    <div className="space-y-6">
      <Card>
        <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-6">
          <SectionHeading as="h2">{t("privacy.heading")}</SectionHeading>

          {/* FIRST, above both boxes. A warning underneath the thing it is about
              is a warning she reads after she has published. */}
          <p className="whitespace-pre-line text-sm text-ink-muted">{privacy.disclaimer_text}</p>

          {documentField(
            "privacy-notice",
            "privacy.noticeLabel",
            notice,
            setNotice,
            privacy.notice_is_default,
            revertNotice,
          )}
          {documentField(
            "privacy-dpa",
            "privacy.dpaLabel",
            dpa,
            setDpa,
            privacy.dpa_is_default,
            revertDpa,
          )}

          {formError !== null && (
            <p role="alert" className="text-sm text-danger">
              {formError}
            </p>
          )}

          <div className="flex items-center gap-3">
            <Button type="submit" loading={saving}>
              {t("privacy.save")}
            </Button>
            {saved && <span className="text-xs text-ink-muted">{t("privacy.saved")}</span>}
          </div>
        </form>
      </Card>

      {/* Read-only, and the ABSENCE of a control is the disclosure (Gate 1 Q3 /
          D14). The list is platform-owned so that one amendment reaches every
          tenant structurally — a boutique may rewrite what she PROMISES about
          processing and may not misstate WHO the processors are. The disclaimer
          above says so in words, so nobody has to guess why the box is missing. */}
      <Card className="space-y-3" data-testid="privacy-subprocessors">
        <h3 className="text-base font-semibold text-ink">{t("privacy.subprocessorsHeading")}</h3>
        <p className="whitespace-pre-line text-sm text-ink-muted">{privacy.subprocessors_text}</p>
      </Card>

      <Card className="space-y-4">
        <SectionHeading as="h2">{t("privacy.subjectHeading")}</SectionHeading>
        {/* The two operational duties NO CODE ENFORCES — the 30-day clock and
            the identity check — stated where the person who owes them stands.
            Both are manual procedure in the compliance record, and this line is
            the only place the console says so. */}
        <p className="text-sm text-ink-muted">{t("privacy.subjectIntro")}</p>

        <div className="flex flex-wrap items-end gap-3">
          <Input
            label={t("privacy.phoneLabel")}
            help={t("privacy.lookupHint")}
            type="tel"
            dir="ltr"
            className="max-w-[240px]"
            value={phone}
            onChange={(event) => {
              setPhone(event.target.value);
              setSubjectError(null);
            }}
          />
          {/* ONE control, TWO outcomes, named for both. The §13 export IS the
              lookup step (D17): the erase and the withdrawal are keyed on
              `customer_id`, and this response is the only place that id comes
              from — step 2 of the erase overwrites `customers.phone`, so a
              phone-keyed erase would destroy its own lookup key. */}
          <Button variant="secondary" size="md" loading={busy} onClick={() => void lookup()}>
            {t("privacy.lookup")}
          </Button>
        </div>

        {subjectError !== null && (
          <p role="alert" className="text-sm text-danger">
            {subjectError}
          </p>
        )}
        {subjectNote !== null && (
          <p role="status" className="text-sm text-ink-muted">
            {subjectNote}
          </p>
        )}

        {subject !== null && (
          <div className="space-y-4 border-t border-border pt-4">
            <p className="text-sm text-ink-muted">
              {t("privacy.subjectLabel")}:{" "}
              <span className="text-ink">
                <bdi>{subject.subject.name}</bdi>
              </span>{" "}
              <bdi dir="ltr">{subject.subject.phone}</bdi>
            </p>
            <a
              className="text-sm text-gold-text underline"
              download={`privacy-export-${subject.subject.id}.json`}
              href={exportHref(subject)}
            >
              {t("privacy.download")}
            </a>

            <TextArea
              label={t("privacy.reasonLabel")}
              // FROM THE API. The «record why, never who» hint is approved legal
              // Hebrew and the audit row it guards is exempt from every retention
              // class forever — writing a phone number into it would put a
              // permanent copy of the identifier in the one table designed never
              // to be erased, inside the action that exists to destroy it.
              help={privacy.erase_reason_hint}
              rows={3}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className="[resize:block]"
            />

            <div className="flex flex-wrap items-center gap-3">
              <Button variant="danger" size="md" disabled={busy} onClick={() => setConfirming(true)}>
                {t("privacy.erase")}
              </Button>
              {/* NO confirmation step, and that is §30A rather than an oversight:
                  revocation may not be conditioned, and a modal asking «are you
                  sure?» at the counter is a condition however small. It is also
                  the lesser action and reversible by asking again. */}
              <Button variant="secondary" size="md" disabled={busy} onClick={() => void withdraw()}>
                {t("privacy.withdraw")}
              </Button>
            </div>

            {confirming && (
              <div className="space-y-3 rounded-md border border-danger p-4">
                <h3 className="text-base font-semibold text-ink">
                  {t("privacy.eraseConfirmTitle")}
                </h3>
                {/* Says what SURVIVES as well as what goes. An owner who expects
                    the row to vanish and finds a booking history the next morning
                    has been told the wrong thing at the one moment she could not
                    undo it. */}
                <p className="text-sm text-ink-muted">{t("privacy.eraseConfirmBody")}</p>
                <Input
                  label={t("privacy.eraseConfirmLabel")}
                  type="tel"
                  dir="ltr"
                  className="max-w-[240px]"
                  value={typedPhone}
                  error={mismatch ? t("privacy.eraseConfirmMismatch") : undefined}
                  onChange={(event) => {
                    setTypedPhone(event.target.value);
                    setMismatch(false);
                  }}
                />
                <div className="flex flex-wrap items-center gap-3">
                  <Button variant="danger" size="md" loading={busy} onClick={() => void erase()}>
                    {t("privacy.eraseConfirmCta")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="md"
                    onClick={() => {
                      setConfirming(false);
                      setTypedPhone("");
                      setMismatch(false);
                    }}
                  >
                    {t("privacy.cancel")}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {subject === null && (
          // Rendered DISABLED rather than omitted: D17's order is the point, and
          // two controls that appear only after a lookup teach nothing about why.
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="danger" size="md" disabled>
              {t("privacy.erase")}
            </Button>
            <Button variant="secondary" size="md" disabled>
              {t("privacy.withdraw")}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
