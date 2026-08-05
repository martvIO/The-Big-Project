import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { Button } from "./Button";

export interface ErrorBoundaryProps {
  /** The outage sentence. Taken as a prop, never resolved here — this package
   * holds no i18n bundle, exactly as `ConsoleShell` takes `logoutLabel`. */
  message: string;
  /** The recovery control's label. */
  reload: string;
  children: ReactNode;
}

interface ErrorBoundaryState {
  failed: boolean;
}

/**
 * The last thing between an uncaught render error and a blank page.
 *
 * ⚠ NEITHER SPA HAD ONE. `grep -rn 'ErrorBoundary|componentDidCatch|
 * getDerivedStateFromError' apps packages` returned zero source hits, and React
 * 19 UNMOUNTS THE WHOLE TREE on an uncaught render error — so any throw in any
 * component left a white page with no text, no control and no way back but a
 * hard reload the user has to think of herself. On the manage console that page
 * is also where the SOS overlay lives, which is why a blank page is not an
 * acceptable failure mode there — this restores a sentence and a reload, NOT the
 * emergency channel itself. A root boundary replaces the overlay too.
 *
 * ⚠ A CLASS, and it has to be: `getDerivedStateFromError` and `componentDidCatch`
 * have no hook equivalent in React 19. This is the one class component in the
 * package and the reason is the API, not a preference.
 *
 * ⚠ It catches RENDER errors only — that is what an error boundary is. An
 * `await` that rejects inside an event handler is not caught here and never
 * was: those are handled where they happen, which is why every section in this
 * product already carries its own outage branch. This is the floor under those,
 * not a replacement for them.
 *
 * The fallback is deliberately tiny: `role="alert"` because she was somewhere in
 * the app when it died, nothing moves focus for her, and no visible control
 * explains the change — the live region is the only thing that says anything
 * happened. `location.reload()` and not a `setState({failed:false})` retry: the
 * tree that threw is the tree that would re-render, and offering a button that
 * reproduces the same crash is worse than offering none.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Not swallowed. There is no error-reporting service wired into this product
    // yet, so the console is the whole of the trail — and a boundary that
    // silently ate the stack would make the one class of bug it exists for the
    // hardest to diagnose.
    console.error("Unhandled render error", error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.failed) {
      return this.props.children;
    }
    return (
      <div
        className="mx-auto flex max-w-[640px] flex-col items-start gap-4 px-4 py-8 text-ink"
        // The page's own direction is on <html>; nothing here forces one.
      >
        <p role="alert" className="max-w-[60ch] text-base text-ink-muted">
          {this.props.message}
        </p>
        <Button variant="secondary" size="md" onClick={() => window.location.reload()}>
          {this.props.reload}
        </Button>
      </div>
    );
  }
}
