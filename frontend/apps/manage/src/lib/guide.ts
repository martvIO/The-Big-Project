// The console's section union, and the guide's step table.
//
// ⚠ THE UNION LIVES HERE AND `App.tsx` IMPORTS IT — never the other way round,
// and that direction is not a preference. Declaring `SectionKey` in `App.tsx`
// and importing it here would build the import cycle `router.tsx:200-214`
// documents, in which `vi.mock`'s live binding silently resolves to the real
// module inside `importActual` and a test passes while asserting nothing.
//
// The union was moved ACROSS AS SHIPPED at F60: same members, same order, same
// ordinal comments. Member order is behaviourally irrelevant, so reordering it
// during the move would have been a diff a reviewer has to read for nothing —
// and it would have cost the record of who added what. F20 appends, for the
// same reason.
export type SectionKey =
  | "dashboard"
  | "profile"
  | "hours"
  | "types"
  | "terms"
  | "catalog"
  | "bookings"
  | "customers"
  | "board"
  | "staff"
  | "gateway"
  // F57's floor — the TWELFTH member since F53 added `customers`.
  | "floor"
  // F33's printable check-in code — the THIRTEENTH.
  | "checkinQr"
  // F41's atelier — the FOURTEENTH.
  | "atelier"
  // F20's privacy documents and subject requests — the FIFTEENTH, and the third
  // owner-only row.
  | "privacy"
  // F22's booking waitlist — the SIXTEENTH. `bookingWaitlist`, not the design
  // sketch's `waitlist`: GuideOverlay derives its dialog title as
  // `t(`nav.${section}`)`, so the key and the labelKey are one spelling by
  // mechanism — and `waitlist` is F58's namespace in this app besides (F-W2).
  | "bookingWaitlist";

// One NON-EMPTY tuple of i18n keys per section, listed in `NAV` order
// (`App.tsx:83-152`), which is deliberately not the union's declaration order
// above — a reader walks the guide in the order the nav offers the sections.
//
// ⚠ `satisfies Record<SectionKey, readonly [string, ...string[]]>` IS THE WHOLE
// MECHANISM. A SIXTEENTH `SectionKey` with no steps is a TYPE ERROR, and a
// section with zero steps is UNREPRESENTABLE — which is how «the button never
// lies» is enforced at the only moment it can be enforced cheaply, since
// `pnpm --filter manage typecheck` gates the merge. There is deliberately NO
// runtime `if (steps.length === 0) return null`: reaching that branch would
// need an injection seam invented solely to test it, and a seam is more code
// than the defect it guards.
//
// ⚠ Every key is a FULL LITERAL, never built from a template. The console's
// `i18n.test.ts` has no source-file scanner, so `HE_F60`'s
// `startsWith("guide.")` filter and its floor are the only things that can see
// a step key — and a filter can only count keys that exist as literals.
export const GUIDE_STEPS = {
  dashboard: ["guide.dashboard.1", "guide.dashboard.2"],
  profile: ["guide.profile.1", "guide.profile.2", "guide.profile.3"],
  hours: ["guide.hours.1", "guide.hours.2", "guide.hours.3"],
  types: ["guide.types.1", "guide.types.2", "guide.types.3"],
  terms: ["guide.terms.1", "guide.terms.2"],
  catalog: ["guide.catalog.1", "guide.catalog.2", "guide.catalog.3"],
  bookings: ["guide.bookings.1", "guide.bookings.2", "guide.bookings.3"],
  customers: ["guide.customers.1", "guide.customers.2"],
  bookingWaitlist: ["guide.bookingWaitlist.1"],
  board: ["guide.board.1", "guide.board.2", "guide.board.3"],
  floor: ["guide.floor.1", "guide.floor.2", "guide.floor.3"],
  atelier: ["guide.atelier.1", "guide.atelier.2", "guide.atelier.3"],
  checkinQr: ["guide.checkinQr.1", "guide.checkinQr.2"],
  staff: ["guide.staff.1", "guide.staff.2"],
  gateway: ["guide.gateway.1", "guide.gateway.2"],
  privacy: ["guide.privacy.1", "guide.privacy.2"],
} as const satisfies Record<SectionKey, readonly [string, ...string[]]>;
