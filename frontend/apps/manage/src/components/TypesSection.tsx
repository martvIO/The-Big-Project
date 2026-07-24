import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { AppointmentType, AppointmentTypeInput } from "../api";
import { agorotFromIlsInput, ilsFromAgorot, validateAppointmentType } from "../validation";
import {
  cardClass,
  dangerButtonClass,
  ErrorNotice,
  inputClass,
  labelClass,
  Loading,
  primaryButtonClass,
  secondaryButtonClass,
} from "./shared";

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
  idPrefix,
  onChange,
}: {
  draft: TypeDraft;
  idPrefix: string;
  onChange: (draft: TypeDraft) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="grow">
        <label className={labelClass} htmlFor={`${idPrefix}-name`}>
          שם
        </label>
        <input
          id={`${idPrefix}-name`}
          className={inputClass}
          value={draft.name}
          onChange={(event) => onChange({ ...draft, name: event.target.value })}
        />
      </div>
      <div>
        <label className={labelClass} htmlFor={`${idPrefix}-duration`}>
          משך (דקות)
        </label>
        <input
          id={`${idPrefix}-duration`}
          type="number"
          min={1}
          max={1440}
          className={inputClass}
          value={draft.durationMinutes}
          onChange={(event) => onChange({ ...draft, durationMinutes: event.target.value })}
        />
      </div>
      <div>
        <label className={labelClass} htmlFor={`${idPrefix}-audience`}>
          קהל יעד
        </label>
        <select
          id={`${idPrefix}-audience`}
          className={inputClass}
          value={draft.audience}
          onChange={(event) =>
            onChange({ ...draft, audience: event.target.value as "all" | "brides_only" })
          }
        >
          <option value="all">כולם</option>
          <option value="brides_only">כלות בלבד</option>
        </select>
      </div>
      <label className="flex items-center gap-2 pb-2 text-sm">
        <input
          type="checkbox"
          checked={draft.depositRequired}
          onChange={(event) => onChange({ ...draft, depositRequired: event.target.checked })}
        />
        נדרשת מקדמה
      </label>
      <div>
        <label className={labelClass} htmlFor={`${idPrefix}-deposit`}>
          מקדמה (₪)
        </label>
        <input
          id={`${idPrefix}-deposit`}
          inputMode="decimal"
          dir="ltr"
          className={inputClass}
          value={draft.depositIls}
          onChange={(event) => onChange({ ...draft, depositIls: event.target.value })}
        />
      </div>
      <div>
        <label className={labelClass} htmlFor={`${idPrefix}-sort`}>
          סדר תצוגה
        </label>
        <input
          id={`${idPrefix}-sort`}
          type="number"
          className={inputClass}
          value={draft.sortOrder}
          onChange={(event) => onChange({ ...draft, sortOrder: event.target.value })}
        />
      </div>
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
    return loadError !== null ? <ErrorNotice message={loadError} /> : <Loading />;
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
    }
  };

  return (
    <div className="space-y-6">
      <section className={`${cardClass} space-y-3`}>
        <h3 className="text-sm font-semibold">סוגי תורים</h3>
        {listError !== null && <ErrorNotice message={listError} />}
        {types.length === 0 ? (
          <p className="text-sm text-stone-500">אין עדיין סוגי תורים — צרי סוג ראשון למטה.</p>
        ) : (
          <ul className="space-y-3">
            {types.map((row) =>
              editingId === row.id ? (
                <li key={row.id} className="space-y-3 rounded border border-stone-200 p-3">
                  <DraftFields draft={editDraft} idPrefix={`edit-${row.id}`} onChange={setEditDraft} />
                  {editError !== null && <ErrorNotice message={editError} />}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className={primaryButtonClass}
                      onClick={() => void handleSaveEdit(row.id)}
                    >
                      שמירה
                    </button>
                    <button
                      type="button"
                      className={secondaryButtonClass}
                      onClick={() => {
                        setEditingId(null);
                        setEditError(null);
                      }}
                    >
                      ביטול
                    </button>
                  </div>
                </li>
              ) : (
                <li
                  key={row.id}
                  className="flex flex-wrap items-center gap-3 border-b border-stone-100 pb-2 text-sm last:border-b-0"
                >
                  <span className="font-medium">{row.name}</span>
                  <span className="text-stone-500">{row.duration_minutes} דקות</span>
                  <span className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-700">
                    {row.audience === "brides_only" ? "כלות בלבד" : "כולם"}
                  </span>
                  {row.deposit_required && row.deposit_amount_agorot !== null ? (
                    <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                      מקדמה {ilsFromAgorot(row.deposit_amount_agorot)} ₪
                    </span>
                  ) : (
                    <span className="text-xs text-stone-400">ללא מקדמה</span>
                  )}
                  <span className="mr-auto flex gap-2">
                    <button
                      type="button"
                      className={secondaryButtonClass}
                      onClick={() => {
                        setEditingId(row.id);
                        setEditDraft(draftFromType(row));
                        setEditError(null);
                      }}
                    >
                      עריכה
                    </button>
                    <button
                      type="button"
                      className={dangerButtonClass}
                      onClick={() => void handleArchive(row.id)}
                    >
                      העברה לארכיון
                    </button>
                  </span>
                </li>
              ),
            )}
          </ul>
        )}
      </section>

      <form onSubmit={(event) => void handleCreate(event)} className={`${cardClass} space-y-3`}>
        <h3 className="text-sm font-semibold">סוג תור חדש</h3>
        <DraftFields draft={createDraft} idPrefix="create" onChange={setCreateDraft} />
        {createError !== null && <ErrorNotice message={createError} />}
        <button type="submit" className={primaryButtonClass} disabled={creating}>
          יצירת סוג תור
        </button>
      </form>
    </div>
  );
}
