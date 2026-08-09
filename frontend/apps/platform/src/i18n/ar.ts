import { he } from "./he";

// Arabic ships with the Hebrew strings verbatim and UNTRANSLATED (Interview Q3 /
// #47, program-wide). The bundle exists so the eventual launch is a translation
// job rather than a retrofit across every feature; no switcher ships, `lng` stays
// "he", and `fallbackLng: "he"` would cover any key this bundle lacked.
//
// Re-exported rather than copied on purpose: two hand-maintained copies drift,
// and `i18n.test.ts`'s key-parity assertion would then pass on the day it
// mattered least and fail on the day somebody added a key to one of them.
export const ar = { translation: { ...he.translation } };
