import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Badge, Button, Card, Input, Modal, Select, Skeleton } from "@boutique/ui";
import { api, ApiError, errorMessage } from "../api";
import type { CreateStaffRequest, StaffMember, StaffRole, UpdateStaffRequest } from "../api";
import { validateStaffDraft } from "../validation";

// The four codes this section speaks Hebrew for. Everything else — including
// VALIDATION_ERROR, which has its own field-local treatment below — falls
// through to errorMessage(error) and shows the server's own text.
//
// NOT pinned by anything. SPEC_ERROR_CODES in backend/tests/test_staff_api.py
// is a Python set checked against a Python module; no test reads this file. A
// fifth staff error code would render in English with a green build, and the
// remedy is to add it here by hand.
const MAPPED_CODES = new Set([
  "DUPLICATE_EMAIL",
  "LAST_OWNER_REQUIRED",
  "STAFF_SELF_MANAGE",
  "NOT_AUTHORIZED",
]);

interface EditDraft {
  displayName: string;
  role: StaffRole;
  password: string;
  currentPassword: string;
}

function draftFrom(row: StaffMember): EditDraft {
  return { displayName: row.display_name, role: row.role, password: "", currentPassword: "" };
}

const EMPTY_CREATE = {
  email: "",
  displayName: "",
  role: "shift_manager" as StaffRole,
  password: "",
};

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
  const [pending, setPending] = useState<StaffMember | null>(null);
  const [listError, setListError] = useState<string | null>(null);

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

  const roleWord = (role: StaffRole): string =>
    role === "owner" ? t("staff.roleOwner") : t("staff.roleShiftManager");

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
    };
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
    try {
      const updated = await api.updateStaff(row.id, body);
      setRows((rows ?? []).map((existing) => (existing.id === row.id ? updated : existing)));
      setEditingId(null);
      setEditDraft(null);
      setEditError(null);
      setCurrentPasswordError(null);
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

  const handleDeactivate = async (row: StaffMember) => {
    try {
      await api.deactivateStaff(row.id);
      setRows((rows ?? []).filter((existing) => existing.id !== row.id));
      setListError(null);
    } catch (error) {
      setListError(message(error));
    } finally {
      setPending(null);
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
                      <option value="owner">{t("staff.roleOwner")}</option>
                      <option value="shift_manager">{t("staff.roleShiftManager")}</option>
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
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setEditingId(null);
                      setEditDraft(null);
                      setEditError(null);
                      setCurrentPasswordError(null);
                    }}
                  >
                    {t("staff.cancelCta")}
                  </Button>
                </div>
              </li>
            ) : (
              <li
                key={row.id}
                className="flex flex-wrap items-center gap-3 border-b border-border pb-2 text-sm last:border-b-0"
              >
                {/* Bare <bdi>: dir="ltr" on a Hebrew name is itself a bidi defect. */}
                <bdi className="font-semibold">{row.display_name}</bdi>
                <bdi dir="ltr" className="text-ink-muted">
                  {row.email}
                </bdi>
                {/* The WORD carries the role; the colour never does. */}
                <Badge variant={row.role === "owner" ? "success" : "neutral"}>
                  {roleWord(row.role)}
                </Badge>
                {isSelf && <span className="text-xs text-ink-muted">{t("staff.selfMarker")}</span>}
                <span className="ms-auto flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setEditingId(row.id);
                      setEditDraft(draftFrom(row));
                      setEditError(null);
                      setCurrentPasswordError(null);
                    }}
                  >
                    {t("staff.editCta")}
                  </Button>
                  {/* No self-deactivate control: the server refuses it with a
                      409, and drawing a door that always refuses is worse than
                      not drawing it. */}
                  {!isSelf && (
                    <Button
                      type="button"
                      variant="danger"
                      onClick={(event) => {
                        deactivateTrigger.current = event.currentTarget;
                        setPending(row);
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
              <option value="owner">{t("staff.roleOwner")}</option>
              <option value="shift_manager">{t("staff.roleShiftManager")}</option>
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
          </div>
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
        title={t("staff.deactivateTitle")}
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setPending(null)}>
              {t("staff.cancelCta")}
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={() => {
                if (pending !== null) {
                  void handleDeactivate(pending);
                }
              }}
            >
              {t("staff.deactivateConfirm")}
            </Button>
          </>
        }
      >
        {/* <Trans>, not t(): the name must land inside a bare <bdi> exactly as
            the list row does. Every founding owner is seeded with
            display_name = owner_email (ProvisioningService.provision), so a
            Latin run with neutral edge characters inside this Hebrew sentence
            is the norm here, not the exception. */}
        <p className="text-sm text-ink">
          <Trans
            i18nKey="staff.deactivateBody"
            values={{ name: pending?.display_name ?? "" }}
            components={{ bdi: <bdi /> }}
          />
        </p>
      </Modal>
    </div>
  );
}
