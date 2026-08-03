import type { StaffRole } from "../api";

/**
 * The role word for every member of the union.
 *
 * ⚠ `Record<StaffRole, string>` IS THE POINT, and it is why this is a record
 * rather than a function with a `default`. Adding a sixth member to `StaffRole`
 * without a key here is a COMPILE error; a switch with a fallback, or the
 * two-branch ternary this replaces, is a wrong label that ships silently.
 *
 * That is not hypothetical — it is the defect F57 would otherwise CREATE.
 * `StaffSection.tsx` resolved the role with
 * `role === "owner" ? t("staff.roleOwner") : t("staff.roleShiftManager")`,
 * which returns «אחראית משמרת» for anything that is not `owner`. Widening the
 * enum without this record labels every seamstress a shift manager on F51's
 * staff screen — the frontend form of "widening the enum widens nothing".
 *
 * In `lib/` so `StaffSection` and `FloorPanel` can both read it without an
 * import cycle (`lib/booking.tsx`'s header gives the general reason).
 */
export const ROLE_LABEL_KEY: Record<StaffRole, string> = {
  owner: "staff.roleOwner",
  shift_manager: "staff.roleShiftManager",
  reception: "staff.roleReception",
  sales_assistant: "staff.roleSalesAssistant",
  seamstress: "staff.roleSeamstress",
};

/**
 * The wire `role` is a plain string (`StaffMember.role`, `StaffCard.role`), so a
 * value outside the union is representable even though the server's CHECK makes
 * it unreachable. Falling back to the raw slug is deliberate: it renders
 * `seamstress` rather than mislabelling her «אחראית משמרת», which is the exact
 * failure mode this module exists to remove.
 */
export function roleLabelKey(role: string): string | null {
  return role in ROLE_LABEL_KEY ? ROLE_LABEL_KEY[role as StaffRole] : null;
}
