import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Badge, Button, Card, Checkbox, DateField, Input, Modal, Select, Skeleton } from "@boutique/ui";
import { api, ApiError, errorMessage, uploadToStorage } from "../api";
import type { CreateStaffRequest, StaffMember, StaffRole, UpdateStaffRequest } from "../api";
import { plainDate, todayJerusalem } from "../lib/jerusalem";
import { ROLE_LABEL_KEY, ROLE_OPTIONS } from "../lib/roles";
import { validateLastDay, validateStaffDraft, validateStaffPhotoFile } from "../validation";

// The nine codes this section speaks Hebrew for. Everything else — including
// VALIDATION_ERROR, which has its own field-local treatment below — falls
// through to errorMessage(error) and shows the server's own text.
//
// NOT pinned by anything. SPEC_ERROR_CODES in backend/tests/test_staff_api.py
// is a Python set checked against a Python module; no test reads this file. A
// tenth staff error code would render in English with a green build, and the
// remedy is to add it here by hand.
const MAPPED_CODES = new Set([
  "DUPLICATE_EMAIL",
  "LAST_OWNER_REQUIRED",
  "STAFF_SELF_MANAGE",
  "NOT_AUTHORIZED",
  // F38's photo pipeline. MEDIA_NOT_CONFIGURED and MEDIA_STORAGE_UNAVAILABLE
  // resolve to one sentence: the owner cannot tell the two apart and does not
  // need to.
  "MEDIA_MISMATCH",
  "MEDIA_NOT_UPLOADED",
  "MEDIA_STORAGE_UNAVAILABLE",
  "MEDIA_NOT_CONFIGURED",
  "TOO_MANY_ATTEMPTS",
]);

// Mirrors the server's accepted set. `multiple` is deliberately absent — one
// photo per person, and the pending/live column pair is what makes replace work.
const PHOTO_ACCEPT = "image/jpeg,image/png,image/webp";

interface EditDraft {
  displayName: string;
  role: StaffRole;
  password: string;
  currentPassword: string;
  // "" is MEANINGFUL on the wire and is the one way to remove a number, so the
  // draft must not coerce it to undefined before comparing.
  phone: string;
  startDate: string;
  eligible: boolean;
}

function draftFrom(row: StaffMember): EditDraft {
  return {
    displayName: row.display_name,
    role: row.role,
    password: "",
    currentPassword: "",
    phone: row.phone ?? "",
    startDate: row.start_date ?? "",
    eligible: row.shift_manager_eligible,
  };
}

// R3: ONE Modal, two bodies. A second <Modal> would duplicate the focus-restore
// effect below, which exists because the trigger unmounts under the open dialog.
type Pending = { kind: "offboard" | "photo"; row: StaffMember };

// The photo control's own state machine, separate from the edit draft because
// its two calls commit IMMEDIATELY: an S3 object cannot participate in a PATCH
// body, and the pending/live pair exists precisely so the old photo keeps
// rendering until the new one confirms.
type PhotoPhase = "idle" | "uploading" | "verifying";

// A DISCRIMINATED value and not a pre-rendered string: the offboard line puts
// her name inside a bare <bdi>, which is markup, and a string carrying literal
// `<bdi>` into a text node is how that isolate silently stops existing.
type Announcement =
  | { kind: "text"; text: string }
  | { kind: "offboarded"; name: string; date: string };

const EMPTY_CREATE = {
  email: "",
  displayName: "",
  role: "shift_manager" as StaffRole,
  password: "",
  phone: "",
  startDate: "",
  eligible: false,
};

// The first GRAPHEME, not `[0]`: a surrogate pair sliced by index renders as a
// replacement character, and `Intl.Segmenter` is in every browser this console
// supports. aria-hidden at every call site — the name is always adjacent.
function initial(name: string): string {
  const trimmed = name.trim();
  if (trimmed === "") {
    return "";
  }
  const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });
  return [...segmenter.segment(trimmed)][0]?.segment ?? "";
}

export function StaffSection({ staffId }: { staffId: string }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<StaffMember[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createDraft, setCreateDraft] = useState(EMPTY_CREATE);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [currentPasswordError, setCurrentPasswordError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [lastDay, setLastDay] = useState("");
  const [lastDayError, setLastDayError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  // ONE role="status" region for the section's terminal outcomes — the offboard
  // confirmation and every photo state. Terminal messages land on the SAME
  // region as the running ones, so a failure is never left silent after a
  // progress message.
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);
  const [photoPhase, setPhotoPhase] = useState<PhotoPhase>("idle");
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [retryable, setRetryable] = useState<File | null>(null);

  const heading = useRef<HTMLHeadingElement>(null);
  const deactivateTrigger = useRef<HTMLButtonElement | null>(null);
  const wasPending = useRef(false);

  useEffect(() => {
    let cancelled = false;
    api
      .listStaff()
      .then((loaded) => {
        if (!cancelled) {
          setRows(loaded);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(t("staff.loadFailed"));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  // The confirm dialog's trigger lives in the row it acts on, so on a successful
  // deactivate it unmounts and native <dialog> focus-return lands on <body>.
  // Cancel restores the trigger; a completed removal falls back to the heading.
  useEffect(() => {
    if (wasPending.current && pending === null) {
      const trigger = deactivateTrigger.current;
      if (trigger !== null && trigger.isConnected) {
        trigger.focus();
      } else {
        heading.current?.focus();
      }
    }
    wasPending.current = pending !== null;
  }, [pending]);

  const message = (error: unknown): string =>
    error instanceof ApiError && MAPPED_CODES.has(error.code)
      ? t(`staff.error.${error.code}`)
      : errorMessage(error);

  // ⚠ Was `role === "owner" ? roleOwner : roleShiftManager`, which returns
  // «אחראית משמרת» for ANYTHING that is not owner. F57 widened StaffRole to five,
  // so left alone this labels every seamstress a shift manager on this screen —
  // the frontend form of "widening the enum widens nothing", and a defect this
  // feature CREATES rather than inherits. ROLE_LABEL_KEY is Record<StaffRole,
  // string>, so a sixth role added without a label is a compile error here.
  const roleWord = (role: StaffRole): string => t(ROLE_LABEL_KEY[role]);

  const closeEditor = () => {
    setEditingId(null);
    setEditDraft(null);
    setEditError(null);
    setCurrentPasswordError(null);
    setPhotoPhase("idle");
    setPhotoError(null);
    setRetryable(null);
  };

  const patchRow = (updated: StaffMember) => {
    setRows((current) => (current ?? []).map((row) => (row.id === updated.id ? updated : row)));
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const invalid = validateStaffDraft({
      display_name: createDraft.displayName,
      email: createDraft.email,
      password: createDraft.password,
    });
    if (invalid !== null) {
      setCreateError(invalid);
      return;
    }
    const body: CreateStaffRequest = {
      email: createDraft.email.trim(),
      display_name: createDraft.displayName.trim(),
      role: createDraft.role,
      password: createDraft.password,
      shift_manager_eligible: createDraft.eligible,
    };
    // Omitted rather than sent blank: on CREATE (unlike the PATCH below) "" has
    // no clear-it meaning, and an empty string would fail the server's phone
    // shape check for a field the owner simply left alone.
    if (createDraft.phone.trim() !== "") {
      body.phone = createDraft.phone.trim();
    }
    if (createDraft.startDate !== "") {
      body.start_date = createDraft.startDate;
    }
    setCreating(true);
    try {
      const created = await api.createStaff(body);
      // Patched from the mutation response rather than refetched: two views that
      // render one object cannot disagree.
      setRows([...(rows ?? []), created]);
      setCreateDraft(EMPTY_CREATE);
      setCreateError(null);
    } catch (error) {
      setCreateError(message(error));
    } finally {
      setCreating(false);
    }
  };

  const handleSave = async (row: StaffMember) => {
    if (editDraft === null) {
      return;
    }
    const isSelf = row.id === staffId;
    const invalid = validateStaffDraft({
      display_name: editDraft.displayName,
      // The edit form has no email field — the address is not editable (D5).
      email: null,
      password: editDraft.password === "" ? null : editDraft.password,
    });
    if (invalid !== null) {
      setEditError(invalid);
      return;
    }
    // Only what actually moved. An all-unchanged patch is a no-op the server
    // answers 200 without writing an audit row, so sending less is not an
    // optimisation — it is what keeps the audit table meaningful.
    const body: UpdateStaffRequest = {};
    if (editDraft.displayName.trim() !== row.display_name) {
      body.display_name = editDraft.displayName.trim();
    }
    if (!isSelf && editDraft.role !== row.role) {
      body.role = editDraft.role;
    }
    if (editDraft.password !== "") {
      body.password = editDraft.password;
      if (isSelf) {
        body.current_password = editDraft.currentPassword;
      }
    }
    // ⚠ `""` IS SENT and is the one way to remove a number — `undefined` already
    // means "not sent" on this API, so coercing the empty string away here would
    // make the clear unreachable from the product.
    if (editDraft.phone.trim() !== (row.phone ?? "")) {
      body.phone = editDraft.phone.trim();
    }
    if (editDraft.startDate !== "" && editDraft.startDate !== row.start_date) {
      body.start_date = editDraft.startDate;
    }
    if (editDraft.eligible !== row.shift_manager_eligible) {
      body.shift_manager_eligible = editDraft.eligible;
    }
    try {
      const updated = await api.updateStaff(row.id, body);
      patchRow(updated);
      closeEditor();
    } catch (error) {
      // The one 400 these forms can produce is a wrong current_password, and the
      // server answers it with an ENGLISH message. Every other 400 is caught
      // client-side by a mirrored bound, which is what makes this field-local
      // Hebrew honest rather than a guess.
      if (error instanceof ApiError && error.status === 400 && isSelf) {
        setCurrentPasswordError(t("staff.currentPasswordWrong"));
        return;
      }
      setEditError(message(error));
    }
  };

  // --- the photo: presign → POST → confirm, committed on its own ---

  const runUpload = async (row: StaffMember, file: File) => {
    setPhotoError(null);
    setRetryable(null);
    setPhotoPhase("uploading");
    setAnnouncement({ kind: "text", text: t("staff.photoUploading") });
    const replacing = row.photo_url !== null;
    try {
      const presign = await api.staffPhotoPresign(row.id, {
        content_type: file.type,
        byte_size: file.size,
      });
      await uploadToStorage(presign, file);
      setPhotoPhase("verifying");
      setAnnouncement({ kind: "text", text: t("staff.photoVerifying") });
      // The magic-byte round trip. Answers the updated member, so the cell
      // re-renders from the server's view rather than from a guess about what
      // the promote did.
      patchRow(await api.staffPhotoConfirm(row.id));
      setAnnouncement({
        kind: "text",
        text: t(replacing ? "staff.photoReplaced" : "staff.photoAdded"),
      });
    } catch (error) {
      // The previous photo is STILL SHOWN — a failed replace never blanks the
      // cell, and nothing above touched the live triple.
      setPhotoError(message(error));
      setRetryable(file);
      setAnnouncement(null);
    } finally {
      setPhotoPhase("idle");
    }
  };

  const handlePhotoPick = async (row: StaffMember, event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    // Cleared so picking the SAME file twice after a failure still fires change.
    event.target.value = "";
    if (file === null) {
      return;
    }
    const reason = validateStaffPhotoFile(file);
    if (reason !== null) {
      // No request and no focus move — focus is still standing in the file
      // input, so the alert has to carry the whole outcome.
      setPhotoError(reason);
      setRetryable(null);
      setAnnouncement(null);
      return;
    }
    await runUpload(row, file);
  };

  const handlePhotoRemove = async (row: StaffMember) => {
    try {
      patchRow(await api.staffPhotoDelete(row.id));
      setPhotoError(null);
      setRetryable(null);
      setAnnouncement({ kind: "text", text: t("staff.photoRemoved") });
    } catch (error) {
      setPhotoError(message(error));
    } finally {
      setPending(null);
    }
  };

  const handleDeactivate = async (row: StaffMember) => {
    const invalid = validateLastDay(lastDay, row.start_date);
    if (invalid !== null) {
      setLastDayError(invalid);
      return;
    }
    try {
      await api.deactivateStaff(row.id, lastDay);
      setRows((rows ?? []).filter((existing) => existing.id !== row.id));
      setListError(null);
      // The row is gone from the list, so this is the ONLY feedback there is.
      setAnnouncement({
        kind: "offboarded",
        name: row.display_name,
        date: plainDate(lastDay),
      });
    } catch (error) {
      setListError(message(error));
    } finally {
      setPending(null);
      setLastDayError(null);
    }
  };

  if (rows === null) {
    return loadError !== null ? (
      <p role="alert" className="text-sm text-ink-muted">
        {loadError}
      </p>
    ) : (
      <Skeleton variant="text" lines={4} />
    );
  }

  return (
    <div className="space-y-6">
      <h2 ref={heading} tabIndex={-1} className="font-display text-xl text-ink">
        {t("staff.heading")}
      </h2>

      {/* ONE region, running AND terminal, and it is never written by anything
          the owner did not initiate. Terminal messages land HERE and not in a
          second region, so a failure is never left silent after a progress
          message. */}
      <p role="status" className="text-sm text-ink">
        {announcement === null
          ? ""
          : announcement.kind === "text"
            ? announcement.text
            : null}
        {announcement !== null && announcement.kind === "offboarded" && (
          <Trans
            i18nKey="staff.offboardDone"
            values={{ name: announcement.name, date: announcement.date }}
            components={{ bdi: <bdi /> }}
          />
        )}
      </p>

      <Card className="space-y-3">
        {listError !== null && (
          <p role="alert" className="text-sm text-danger">
            {listError}
          </p>
        )}
        <ul className="space-y-3">
          {rows.map((row) => {
            const isSelf = row.id === staffId;
            return editingId === row.id && editDraft !== null ? (
              <li key={row.id} className="space-y-3 rounded border border-border p-3">
                <div className="flex flex-wrap items-end gap-3">
                  <div className="grow">
                    <Input
                      label={t("staff.displayNameLabel")}
                      value={editDraft.displayName}
                      onChange={(event) =>
                        setEditDraft({ ...editDraft, displayName: event.target.value })
                      }
                    />
                  </div>
                  {!isSelf && (
                    <Select
                      label={t("staff.roleLabel")}
                      value={editDraft.role}
                      onChange={(event) =>
                        setEditDraft({ ...editDraft, role: event.target.value as StaffRole })
                      }
                    >
                      {ROLE_OPTIONS.map((value) => (
                        <option key={value} value={value}>
                          {t(ROLE_LABEL_KEY[value])}
                        </option>
                      ))}
                    </Select>
                  )}
                  <Input
                    label={t("staff.newPasswordLabel")}
                    help={t("staff.newPasswordHelp")}
                    type="password"
                    autoComplete="new-password"
                    value={editDraft.password}
                    onChange={(event) =>
                      setEditDraft({ ...editDraft, password: event.target.value })
                    }
                  />
                  {isSelf && editDraft.password !== "" && (
                    <Input
                      label={t("staff.currentPasswordLabel")}
                      help={t("staff.currentPasswordHelp")}
                      type="password"
                      autoComplete="current-password"
                      error={currentPasswordError ?? undefined}
                      value={editDraft.currentPassword}
                      onChange={(event) =>
                        setEditDraft({ ...editDraft, currentPassword: event.target.value })
                      }
                    />
                  )}
                  {/* CONTACT ONLY (spec C1): the help line says so, because a
                      phone field on a staff row reads like a second login. */}
                  <Input
                    label={t("staff.phoneLabel")}
                    help={t("staff.phoneHelp")}
                    type="tel"
                    dir="ltr"
                    autoComplete="off"
                    value={editDraft.phone}
                    onChange={(event) => setEditDraft({ ...editDraft, phone: event.target.value })}
                  />
                  <DateField
                    label={t("staff.startDateLabel")}
                    value={editDraft.startDate}
                    onChange={(event) =>
                      setEditDraft({ ...editDraft, startDate: event.target.value })
                    }
                  />
                </div>
                {/* Checkbox and not Toggle: role="switch" is on/off — a setting
                    that takes effect. Eligibility is a recorded FACT about a
                    person that F38 enforces nowhere (F40 is its only consumer),
                    which is checked/unchecked. */}
                <Checkbox
                  label={t("staff.eligibleLabel")}
                  description={t("staff.eligibleHelp")}
                  checked={editDraft.eligible}
                  onCheckedChange={(checked) => setEditDraft({ ...editDraft, eligible: checked })}
                />

                <div className="flex flex-wrap items-start gap-3">
                  {row.photo_url === null ? (
                    <span
                      aria-hidden="true"
                      className="flex size-22 shrink-0 items-center justify-center rounded-sm bg-surface text-base text-ink-muted"
                    >
                      {initial(row.display_name)}
                    </span>
                  ) : (
                    /* alt="" deliberately: the display name is a text node in
                       the same panel, so the image adds nothing a screen-reader
                       user can use. It is the definition of decorative. */
                    <img
                      src={row.photo_url}
                      alt=""
                      className="size-22 shrink-0 rounded-sm object-cover"
                    />
                  )}
                  <div className="grow space-y-2">
                    {/* A REAL, VISIBLE, FOCUSABLE file input — never display:none
                        plus a label shim, which breaks Safari/VoiceOver and
                        hides the disabled reason. The purpose line rides the
                        `help` slot, which Input links with aria-describedby, so
                        it is announced AT CAPTURE and not parked in a footnote. */}
                    <Input
                      label={t(
                        row.photo_url === null
                          ? "staff.photoUploadLabel"
                          : "staff.photoReplaceLabel",
                      )}
                      help={`${t("staff.photoPurpose")} ${t("staff.photoFormats")}`}
                      type="file"
                      accept={PHOTO_ACCEPT}
                      disabled={photoPhase !== "idle"}
                      onChange={(event) => void handlePhotoPick(row, event)}
                    />
                    {photoError !== null && (
                      <p role="alert" className="text-sm text-danger">
                        {photoError}
                      </p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      {retryable !== null && (
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={photoPhase !== "idle"}
                          onClick={() => void runUpload(row, retryable)}
                        >
                          {t("staff.photoRetryCta")}
                        </Button>
                      )}
                      {row.photo_url !== null && (
                        <Button
                          type="button"
                          variant="danger"
                          disabled={photoPhase !== "idle"}
                          onClick={() => setPending({ kind: "photo", row })}
                        >
                          {t("staff.photoRemoveCta")}
                        </Button>
                      )}
                    </div>
                  </div>
                </div>

                {editError !== null && (
                  <p role="alert" className="text-sm text-danger">
                    {editError}
                  </p>
                )}
                <div className="flex gap-2">
                  <Button type="button" onClick={() => void handleSave(row)}>
                    {t("staff.saveCta")}
                  </Button>
                  <Button type="button" variant="secondary" onClick={closeEditor}>
                    {t("staff.cancelCta")}
                  </Button>
                </div>
              </li>
            ) : (
              <li
                key={row.id}
                className="flex flex-wrap items-center gap-3 border-b border-border pb-2 text-sm last:border-b-0"
              >
                {row.photo_url === null ? (
                  <span
                    aria-hidden="true"
                    className="flex size-11 shrink-0 items-center justify-center rounded-full bg-surface text-base text-ink-muted"
                  >
                    {initial(row.display_name)}
                  </span>
                ) : (
                  <img
                    src={row.photo_url}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="size-11 shrink-0 rounded-full object-cover"
                  />
                )}
                {/* Bare <bdi>: dir="ltr" on a Hebrew name is itself a bidi defect. */}
                <bdi className="font-semibold">{row.display_name}</bdi>
                <bdi dir="ltr" className="text-ink-muted">
                  {row.email}
                </bdi>
                {/* The WORD carries the role; the colour never does. */}
                <Badge variant={row.role === "owner" ? "success" : "neutral"}>
                  {roleWord(row.role)}
                </Badge>
                {/* MUTED WORDS, never a second Badge: the row already carries the
                    role pill, and F36's ruling is one pill per row so the pill
                    means one thing. */}
                {row.shift_manager_eligible && (
                  <span className="text-xs text-ink-muted">{t("staff.eligibleLabel")}</span>
                )}
                {isSelf && <span className="text-xs text-ink-muted">{t("staff.selfMarker")}</span>}
                {/* ⚠ BOTH CONTROLS ARE NAMED AFTER THE ROW, and both were
                    nameless: seven staff meant seven identical «עריכה» and six
                    identical «סיום העסקה» in one list, one of which ends a
                    colleague's access. «{action} — {name}» is the console's own
                    shape — the floor, waitlist and atelier panels all use it —
                    and the visible word leads so WCAG 2.5.3 holds for speech
                    input. No bidi markup: an aria-label takes none. */}
                <span className="ms-auto flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    aria-label={t("staff.editAria", { name: row.display_name })}
                    onClick={() => {
                      setEditingId(row.id);
                      setEditDraft(draftFrom(row));
                      setEditError(null);
                      setCurrentPasswordError(null);
                      setPhotoError(null);
                      setRetryable(null);
                    }}
                  >
                    {t("staff.editCta")}
                  </Button>
                  {/* No self-offboard control: the server refuses it with a
                      409, and drawing a door that always refuses is worse than
                      not drawing it. */}
                  {!isSelf && (
                    <Button
                      type="button"
                      variant="danger"
                      aria-label={t("staff.deactivateAria", { name: row.display_name })}
                      onClick={(event) => {
                        deactivateTrigger.current = event.currentTarget;
                        // Defaulted to today JERUSALEM. A blank would silently
                        // exempt her from the retention clock — the policy's
                        // predicate needs `last_day IS NOT NULL`.
                        setLastDay(todayJerusalem());
                        setLastDayError(null);
                        setPending({ kind: "offboard", row });
                      }}
                    >
                      {t("staff.deactivateCta")}
                    </Button>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card>
        <form onSubmit={(event) => void handleCreate(event)} className="space-y-3">
          <h3 className="text-sm font-semibold">{t("staff.createHeading")}</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div className="grow">
              <Input
                label={t("staff.emailLabel")}
                type="email"
                dir="ltr"
                autoComplete="off"
                value={createDraft.email}
                onChange={(event) => setCreateDraft({ ...createDraft, email: event.target.value })}
              />
            </div>
            <div className="grow">
              <Input
                label={t("staff.displayNameLabel")}
                value={createDraft.displayName}
                onChange={(event) =>
                  setCreateDraft({ ...createDraft, displayName: event.target.value })
                }
              />
            </div>
            <Select
              label={t("staff.roleLabel")}
              value={createDraft.role}
              onChange={(event) =>
                setCreateDraft({ ...createDraft, role: event.target.value as StaffRole })
              }
            >
              {ROLE_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {t(ROLE_LABEL_KEY[value])}
                </option>
              ))}
            </Select>
            <Input
              label={t("staff.passwordLabel")}
              type="password"
              // Without this the owner's browser offers her HER OWN console
              // credential for the new staffer's account — a real way to create
              // an account nobody can sign into.
              autoComplete="new-password"
              value={createDraft.password}
              onChange={(event) => setCreateDraft({ ...createDraft, password: event.target.value })}
            />
            <Input
              label={t("staff.phoneLabel")}
              help={t("staff.phoneHelp")}
              type="tel"
              dir="ltr"
              autoComplete="off"
              value={createDraft.phone}
              onChange={(event) => setCreateDraft({ ...createDraft, phone: event.target.value })}
            />
            <DateField
              label={t("staff.startDateLabel")}
              value={createDraft.startDate}
              onChange={(event) =>
                setCreateDraft({ ...createDraft, startDate: event.target.value })
              }
            />
          </div>
          <Checkbox
            label={t("staff.eligibleLabel")}
            description={t("staff.eligibleHelp")}
            checked={createDraft.eligible}
            onCheckedChange={(checked) => setCreateDraft({ ...createDraft, eligible: checked })}
          />
          {/* No photo control on the create form: the presign route needs a
              staff id, which does not exist until the row does. She gets one
              from her own edit panel a moment later. */}
          <p className="text-xs text-ink-muted">{t("staff.passwordNotice")}</p>
          {createError !== null && (
            <p role="alert" className="text-sm text-danger">
              {createError}
            </p>
          )}
          <Button type="submit" disabled={creating}>
            {t("staff.createCta")}
          </Button>
        </form>
      </Card>

      <Modal
        open={pending !== null}
        onClose={() => setPending(null)}
        title={t(pending?.kind === "photo" ? "staff.photoRemoveTitle" : "staff.deactivateTitle")}
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setPending(null)}>
              {t("staff.cancelCta")}
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={() => {
                if (pending === null) {
                  return;
                }
                if (pending.kind === "photo") {
                  void handlePhotoRemove(pending.row);
                } else {
                  void handleDeactivate(pending.row);
                }
              }}
            >
              {t(
                pending?.kind === "photo"
                  ? "staff.photoRemoveConfirm"
                  : "staff.deactivateConfirm",
              )}
            </Button>
          </>
        }
      >
        {pending?.kind === "photo" ? (
          <p className="text-sm text-ink">{t("staff.photoRemoveBody")}</p>
        ) : (
          <div className="space-y-3">
            {/* <Trans>, not t(): the name must land inside a bare <bdi> exactly as
                the list row does. Every founding owner is seeded with
                display_name = owner_email (ProvisioningService.provision), so a
                Latin run with neutral edge characters inside this Hebrew sentence
                is the norm here, not the exception. */}
            <p className="text-sm text-ink">
              <Trans
                i18nKey="staff.deactivateBody"
                values={{ name: pending?.row.display_name ?? "" }}
                components={{ bdi: <bdi /> }}
              />
            </p>
            <DateField
              label={t("staff.lastDayLabel")}
              help={t("staff.lastDayHelp")}
              error={lastDayError ?? undefined}
              value={lastDay}
              onChange={(event) => {
                setLastDay(event.target.value);
                setLastDayError(null);
              }}
            />
            {/* Plain and unhedged: what is kept, what is erased and when, and
                that a return is a new record. */}
            <p className="text-sm text-ink-muted">{t("staff.offboardRetentionNote")}</p>
          </div>
        )}
      </Modal>
    </div>
  );
}
