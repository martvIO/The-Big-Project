import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { ar } from "./ar";
import { he } from "./he";

// Hebrew-default, and Hebrew is the only locale a visitor can reach in v1.
// escapeValue: false — React already escapes, double-escaping would corrupt
// Hebrew punctuation.
//
// `ar` is registered but NOT selectable: Interview Q3 ships Arabic keys from F16
// onward, untranslated, so the eventual launch is a translation job rather than a
// retrofit across ~28 features. No switcher exists, `lng` stays "he", and
// `fallbackLng: "he"` covers every key the partial `ar` bundle does not carry.
void i18n.use(initReactI18next).init({
  resources: { he: { translation: he.translation }, ar: { translation: ar.translation } },
  lng: "he",
  fallbackLng: "he",
  interpolation: { escapeValue: false },
});

export default i18n;
