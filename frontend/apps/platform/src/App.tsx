import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "./api";
import type { Operator } from "./api";
import { Console } from "./components/Console";
import { LoginPanel } from "./components/LoginPanel";

// The manage app's no-client-router pattern: one screen, driven from useState.
// `GET /platform/auth/me` is the whole bootstrap — 401 renders the login panel,
// 200 renders the console.
export function App() {
  const { t } = useTranslation();
  const [operator, setOperator] = useState<Operator | null>(null);
  const [ready, setReady] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
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
  }, []);

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

  useEffect(() => {
    if (operator === null) return;
    const onRejection = (event: PromiseRejectionEvent) => {
      if (event.reason instanceof ApiError && event.reason.status === 401) {
        signOut(true);
      }
    };
    window.addEventListener("unhandledrejection", onRejection);
    return () => window.removeEventListener("unhandledrejection", onRejection);
  }, [operator, signOut]);

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
