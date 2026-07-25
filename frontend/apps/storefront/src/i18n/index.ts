import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { he } from "./he";

// Hebrew-default, single locale. escapeValue: false — React already escapes,
// double-escaping would corrupt Hebrew punctuation.
void i18n.use(initReactI18next).init({
  resources: { he: { translation: he.translation } },
  lng: "he",
  fallbackLng: "he",
  interpolation: { escapeValue: false },
});

export default i18n;
