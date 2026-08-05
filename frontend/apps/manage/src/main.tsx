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
// with no text and no control. `App.test.tsx` asserts this wiring, because a
// build cannot.
//
// ⚠ THIS DOES NOT PRESERVE THE SOS CHANNEL, and nothing here should be read as
// claiming it does: the boundary is at the ROOT, so a throw in the atelier board
// or the staff list replaces the SOS overlay along with everything else. That is
// the prescribed shape — one boundary per app root — and it buys the one thing
// the blank page did not offer, a sentence and a reload. Surviving the crash as
// a working emergency channel would need a second boundary AROUND the overlay,
// which is a decision nobody has taken; it is not what this is.
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
