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

// The boundary wraps `<App/>` and nothing may sit between them — React 19
// unmounts the whole tree on an uncaught render error, and this console has
// exactly one screen, so a throw would leave a blank white page with no text and
// no control. Both strings are lifted verbatim from the manage app's equivalents (see
// i18n/he.ts) — the design deck covers no crash state, and inventing a register
// at the one place copy cannot be reviewed in context is how one gets invented.
createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary
      message={i18n.t("platform.crash.body")}
      reload={i18n.t("platform.crash.reload")}
    >
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
