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
// unmounts the whole tree on an uncaught render error, and this console had no
// boundary anywhere — a throw in any of fourteen sections left a blank white page
// with no text and no control, on the surface that is ALSO the SOS emergency
// channel. `App.test.tsx` asserts this wiring, because a build cannot.
//
// `i18n.t` and not `useTranslation`: a boundary is a class component and this is
// module scope. Both strings are existing keys — the console's own outage
// sentence and the reload label its board and floor panels already use — so no
// new copy is introduced at the one place copy cannot be reviewed in context.
createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary message={i18n.t("dashboard.loadFailed")} reload={i18n.t("board.reload")}>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
