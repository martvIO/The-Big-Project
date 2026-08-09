import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input } from "@boutique/ui";
import { ApiError, api } from "../api";
import type { Operator } from "../api";
import markUrl from "../assets/modryn-mark.svg";

// The manage LoginForm's shape, verbatim where it matters: the lockup IS the
// heading (one h1 per screen, and the full Hebrew title still reaches assistive
// tech through the sr-only span), the mark is decorative, the Latin wordmark is
// aria-hidden or both would be announced twice over.
export function LoginPanel({
  onLogin,
  notice,
}: {
  onLogin: (operator: Operator) => void;
  // The mid-session expiry line (design §Screen 1). `role="status"` and not
  // `role="alert"`: nothing went wrong, the session simply ended, and the calm
  // register is the design's own ruling.
  notice?: string | null;
}) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLogin(await api.login(email, password));
    } catch (loginError) {
      // ⚠ ONE SENTENCE FOR WRONG PASSWORD AND FOR UNKNOWN ADDRESS. The server
      // is timing-equalized and answers one body either way (spec D4); the UI
      // must not undo that by distinguishing them. Only the 429 gets its own
      // sentence, because "wait" is a different instruction from "try again".
      const tooMany = loginError instanceof ApiError && loginError.status === 429;
      setError(t(tooMany ? "platform.login.tooMany" : "platform.login.failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 text-ink">
      <form onSubmit={(event) => void handleSubmit(event)} className="w-full max-w-sm">
        <h1 className="mb-8 flex flex-col items-center gap-3">
          <img src={markUrl} alt="" width={64} height={64} className="h-16 w-16" />
          <span
            aria-hidden="true"
            dir="ltr"
            className="font-display text-2xl tracking-[0.02em] text-ink"
          >
            MODRYN
          </span>
          <span className="sr-only">{t("platform.login.title")}</span>
        </h1>
        {notice != null && (
          <p role="status" className="mb-4 text-center text-sm text-ink-muted">
            {notice}
          </p>
        )}
        <Card className="flex flex-col gap-4">
          <Input
            label={t("platform.login.email")}
            type="email"
            dir="ltr"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Input
            label={t("platform.login.password")}
            type="password"
            dir="ltr"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error !== null && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" loading={busy}>
            {t("platform.login.submit")}
          </Button>
        </Card>
      </form>
    </main>
  );
}
