import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Badge, Button, Card, Input, Modal, Select, Skeleton, Toggle } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { AppointmentType, AppointmentTypeInput } from "../api";
import { agorotFromIlsInput, ilsFromAgorot, validateAppointmentType } from "../validation";

interface TypeDraft {
  name: string;
  durationMinutes: string;
  audience: "all" | "brides_only";
  depositRequired: boolean;
  depositIls: string;
  sortOrder: string;
}

const emptyDraft: TypeDraft = {
  name: "",
  durationMinutes: "60",
  audience: "all",
  depositRequired: false,
  depositIls: "",
  sortOrder: "0",
};

function draftFromType(appointmentType: AppointmentType): TypeDraft {
  return {
    name: appointmentType.name,
    durationMinutes: String(appointmentType.duration_minutes),
    audience: appointmentType.audience,
    depositRequired: appointmentType.deposit_required,
    depositIls:
      appointmentType.deposit_amount_agorot === null
        ? ""
        : ilsFromAgorot(appointmentType.deposit_amount_agorot),
    sortOrder: String(appointmentType.sort_order),
  };
}

// Money travels as integer agorot on the wire; the owner types ILS.
function toInput(draft: TypeDraft): AppointmentTypeInput | string {
  let depositAgorot: number | null = null;
  if (draft.depositIls.trim() !== "") {
    depositAgorot = agorotFromIlsInput(draft.depositIls);
    if (depositAgorot === null) {
      return "סכום המקדמה אינו תקין (שקלים, עד שתי ספרות אחרי הנקודה)";
    }
  }
  const input: AppointmentTypeInput = {
    name: draft.name.trim(),
    duration_minutes: Number(draft.durationMinutes),
    audience: draft.audience,
    deposit_required: draft.depositRequired,
    deposit_amount_agorot: depositAgorot === 0 ? null : depositAgorot,
    sort_order: Number(draft.sortOrder) || 0,
  };
  const invalid = validateAppointmentType({
    name: input.name,
    duration_minutes: input.duration_minutes,
    deposit_required: input.deposit_required,
    deposit_amount_agorot: input.deposit_amount_agorot,
  });
  return invalid ?? input;
}

function DraftFields({
  draft,
  onChange,
}: {
  draft: TypeDraft;
  onChange: (draft: TypeDraft) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="grow">
        <Input
          label="שם"
          value={draft.name}
          onChange={(event) => onChange({ ...draft, name: event.target.value })}
        />
      </div>
      <Input
        label="משך (דקות)"
        type="number"
        min={1}
        max={1440}
        value={draft.durationMinutes}
        onChange={(event) => onChange({ ...draft, durationMinutes: event.target.value })}
      />
      <Select
        label="קהל יעד"
        value={draft.audience}
        onChange={(event) =>
          onChange({ ...draft, audience: event.target.value as "all" | "brides_only" })
        }
      >
        <option value="all">כולם</option>
        <option value="brides_only">כלות בלבד</option>
      </Select>
      <Toggle
        label="נדרשת מקדמה"
        checked={draft.depositRequired}
        onCheckedChange={(checked) => onChange({ ...draft, depositRequired: checked })}
      />
      <Input
        label="מקדמה (₪)"
        inputMode="decimal"
        dir="ltr"
        value={draft.depositIls}
        onChange={(event) => onChange({ ...draft, depositIls: event.target.value })}
      />
      <Input
        label="סדר תצוגה"
        type="number"
        value={draft.sortOrder}
        onChange={(event) => onChange({ ...draft, sortOrder: event.target.value })}
      />
    </div>
  );
}

export function TypesSection() {
  const [types, setTypes] = useState<AppointmentType[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createDraft, setCreateDraft] = useState<TypeDraft>(emptyDraft);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<TypeDraft>(emptyDraft);
  const [editError, setEditError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [pendingArchive, setPendingArchive] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listAppointmentTypes()
      .then((rows) => {
        if (!cancelled) {
          setTypes(rows);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(errorMessage(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (types === null) {
    return loadError !== null ? (
      <p role="alert" className="text-sm text-ink-muted">
        {loadError}
      </p>
    ) : (
      <Skeleton variant="text" lines={4} />
    );
  }

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input = toInput(createDraft);
    if (typeof input === "string") {
      setCreateError(input);
      return;
    }
    setCreating(true);
    try {
      const created = await api.createAppointmentType(input);
      setTypes([...types, created]);
      setCreateDraft(emptyDraft);
      setCreateError(null);
    } catch (error) {
      setCreateError(errorMessage(error));
    } finally {
      setCreating(false);
    }
  };

  const handleSaveEdit = async (id: string) => {
    const input = toInput(editDraft);
    if (typeof input === "string") {
      setEditError(input);
      return;
    }
    try {
      const updated = await api.updateAppointmentType(id, input);
      setTypes(types.map((row) => (row.id === id ? updated : row)));
      setEditingId(null);
      setEditError(null);
    } catch (error) {
      setEditError(errorMessage(error));
    }
  };

  const handleArchive = async (id: string) => {
    try {
      await api.archiveAppointmentType(id);
      setTypes(types.filter((row) => row.id !== id));
      setListError(null);
    } catch (error) {
      setListError(errorMessage(error));
    } finally {
      setPendingArchive(null);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="space-y-3">
        <h3 className="text-sm font-semibold">סוגי תורים</h3>
        {listError !== null && (
          <p role="alert" className="text-sm text-danger">
            {listError}
          </p>
        )}
        {types.length === 0 ? (
          <p className="text-sm text-ink-muted">אין עדיין סוגי תורים — צרי סוג ראשון למטה.</p>
        ) : (
          <ul className="space-y-3">
            {types.map((row) =>
              editingId === row.id ? (
                <li key={row.id} className="space-y-3 rounded border border-border p-3">
                  <DraftFields draft={editDraft} onChange={setEditDraft} />
                  {editError !== null && (
                    <p role="alert" className="text-sm text-danger">
                      {editError}
                    </p>
                  )}
                  <div className="flex gap-2">
                    <Button type="button" onClick={() => void handleSaveEdit(row.id)}>
                      שמירה
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        setEditingId(null);
                        setEditError(null);
                      }}
                    >
                      ביטול
                    </Button>
                  </div>
                </li>
              ) : (
                <li
                  key={row.id}
                  className="flex flex-wrap items-center gap-3 border-b border-border pb-2 text-sm last:border-b-0"
                >
                  <span className="font-medium">{row.name}</span>
                  <span className="text-ink-muted">{row.duration_minutes} דקות</span>
                  <Badge variant="neutral">
                    {row.audience === "brides_only" ? "כלות בלבד" : "כולם"}
                  </Badge>
                  {row.deposit_required && row.deposit_amount_agorot !== null ? (
                    <Badge variant="warning">מקדמה {ilsFromAgorot(row.deposit_amount_agorot)} ₪</Badge>
                  ) : (
                    <span className="text-xs text-ink-muted">ללא מקדמה</span>
                  )}
                  <span className="ms-auto flex gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        setEditingId(row.id);
                        setEditDraft(draftFromType(row));
                        setEditError(null);
                      }}
                    >
                      עריכה
                    </Button>
                    <Button
                      type="button"
                      variant="danger"
                      onClick={() => setPendingArchive(row.id)}
                    >
                      העברה לארכיון
                    </Button>
                  </span>
                </li>
              ),
            )}
          </ul>
        )}
      </Card>

      <Card>
        <form onSubmit={(event) => void handleCreate(event)} className="space-y-3">
          <h3 className="text-sm font-semibold">סוג תור חדש</h3>
          <DraftFields draft={createDraft} onChange={setCreateDraft} />
          {createError !== null && (
            <p role="alert" className="text-sm text-danger">
              {createError}
            </p>
          )}
          <Button type="submit" disabled={creating}>
            יצירת סוג תור
          </Button>
        </form>
      </Card>

      <Modal
        open={pendingArchive !== null}
        onClose={() => setPendingArchive(null)}
        title="העברה לארכיון"
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setPendingArchive(null)}>
              ביטול
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={() => {
                if (pendingArchive !== null) {
                  void handleArchive(pendingArchive);
                }
              }}
            >
              העברה לארכיון
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink">להעביר את סוג התור לארכיון?</p>
      </Modal>
    </div>
  );
}
