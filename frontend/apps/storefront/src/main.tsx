import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ErrorBoundary } from "@boutique/ui";
import { App } from "./App";
import i18n from "./i18n";
import "./index.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found");
}

// ⚠ THE BOUNDARY WRAPS `<App/>` AND NOTHING ELSE MAY SIT BETWEEN THEM. React 19
// unmounts the whole tree on an uncaught render error, and this app had no
// boundary anywhere — a throw in any route left a bride on a blank white page
// with no text and no control. `router.test.tsx` asserts this wiring, because a
// build cannot.
//
// `i18n.t` and not `useTranslation`: a boundary is a class component and this is
// module scope. Both strings are existing keys — the storefront's own unexpected
// -failure sentence and the catalog's retry label — so no new copy is introduced
// at the one place copy cannot be reviewed in context.
createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary message={i18n.t("errors.unknown")} reload={i18n.t("catalog.retry")}>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
