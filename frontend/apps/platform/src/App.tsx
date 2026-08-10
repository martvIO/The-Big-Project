import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, onSessionExpired } from "./api";
import type { Operator } from "./api";
import { Console } from "./components/Console";
import { JoinPanel } from "./components/JoinPanel";
import { LoginPanel } from "./components/LoginPanel";

// F26 D1. The redeemer's screen is served from THIS bundle at a second exact
// path (`main.py`'s `_serve_file`), because the apex 404s by design, the tenant
// host does not exist until redemption succeeds, and a new label would cost a
// fourth workspace app for one form.
const JOIN_PATH = "/platform/join";

// The manage app's no-client-router pattern: one screen, driven from useState.
// `GET /platform/auth/me` is the whole bootstrap — 401 renders the login panel,
// 200 renders the console.
export function App() {
  const { t } = useTranslation();
  // ⚠ READ ONCE, AND THE BRANCH IS BEFORE THE BOOTSTRAP. The redeemer is not an
  // operator and has no session: calling `/platform/auth/me` for her would be a
  // guaranteed 401 on every load, one pointless round trip on the one screen a
  // non-operator opens, most likely on a phone. There is no client router, so
  // the path cannot change under the app.
  const isJoin = window.location.pathname === JOIN_PATH;
  const [operator, setOperator] = useState<Operator | null>(null);
  const [ready, setReady] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (isJoin) return;
    let cancelled = false;
    api
      .me()
      .then((me) => {
        if (!cancelled) setOperator(me);
      })
      .catch(() => {
        // Every failure lands on the login panel, including a network one. There
        // is nothing else this app can show: it has exactly one authenticated
        // screen, and a spinner that never resolves is worse than a form.
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [isJoin]);

  // ⚠ A MID-SESSION 401 FLIPS BACK TO THE LOGIN PANEL WITH A CALM LINE, not an
  // error one. The 4h TTL is fixed and nothing slides it, so a working console
  // WILL expire under an operator mid-task; «ההתחברות הסתיימה» states that as a
  // fact. It does not pretend her in-progress form values survived, because they
  // did not.
  const signOut = useCallback(
    (expired: boolean) => {
      setOperator(null);
      setNotice(expired ? t("platform.login.sessionExpired") : null);
    },
    [t],
  );

  // Subscribed at the FETCH layer and not to `unhandledrejection`: every call
  // site in Console.tsx catches its own ApiError to render a refusal sentence, so
  // no 401 ever surfaces as an unhandled rejection and the listener this replaces
  // fired for none of the paths above. Registered only while signed in, so the
  // bootstrap 401 and a refused login stay on the login screen's own copy.
  useEffect(() => {
    if (operator === null) return;
    onSessionExpired(() => signOut(true));
    return () => onSessionExpired(null);
  }, [operator, signOut]);

  // Before the `ready` gate, which the join screen never sets: nothing on this
  // path waits on the console's bootstrap.
  if (isJoin) return <JoinPanel />;
  if (!ready) return null;
  if (operator === null) {
    return (
      <LoginPanel
        notice={notice}
        onLogin={(me) => {
          setNotice(null);
          setOperator(me);
        }}
      />
    );
  }
  return <Console operator={operator} onSignedOut={() => signOut(false)} />;
}
