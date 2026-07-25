import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { Staff } from "../api";

export function LoginForm({ onLogin }: { onLogin: (staff: Staff) => void }) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    try {
      onLogin(await api.login(email, password));
    } catch (loginError) {
      // Generic message preserved verbatim from the API (F5 anti-enumeration).
      setError(errorMessage(loginError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 text-ink">
      <form onSubmit={(event) => void handleSubmit(event)} className="w-full max-w-sm">
        <Card className="flex flex-col gap-4">
          <h1 className="font-display text-xl text-ink">{t("login.title")}</h1>
          <Input
            label={t("login.email")}
            type="email"
            dir="ltr"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Input
            label={t("login.password")}
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
            {t("login.submit")}
          </Button>
        </Card>
      </form>
    </main>
  );
}
