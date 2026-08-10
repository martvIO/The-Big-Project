import type { OnShiftSource } from "../api";

// ⚠ NO FALLBACK, DELIBERATELY — `lib/roles.ts`' `ROLE_LABEL_KEY` argument
// verbatim. A `Record<OnShiftSource, string>` is TOTAL, so the day a fourth
// source arrives on the wire this file is a COMPILE ERROR rather than a card
// silently rendering the wrong Hebrew phrase. F57's recorded near-miss is the
// reason the rule exists: a two-branch ternary that printed «אחראית משמרת» for
// every seamstress, and shipped.
//
// ⚠ THE CLIENT NEVER INFERS THE RULE (spec D8). The server computes the answer
// and the rule TOGETHER, in one tuple, precisely so they cannot disagree; this
// map only turns the server's enum into the phrase beside it.
//
// `fallback` still maps to a string even though a `fallback` card renders NO
// on-shift line (design §6.2): the `Record` stays total, and what moved is the
// RENDER SITE — the sentence goes once above the list instead of eight times
// down it.
export const ON_SHIFT_SOURCE_KEY: Record<OnShiftSource, string> = {
  manual_today: "floor.onShiftManualToday",
  roster: "floor.onShiftRoster",
  fallback: "floor.onShiftNoRoster",
};
