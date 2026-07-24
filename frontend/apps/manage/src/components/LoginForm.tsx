import { useState } from "react";
import type { FormEvent } from "react";
import { tokens } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { Staff } from "../api";
import { cardClass, ErrorNotice, inputClass, labelClass, primaryButtonClass } from "./shared";

export function LoginForm({ onLogin }: { onLogin: (staff: Staff) => void }) {
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
      setError(errorMessage(loginError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main
      className="flex min-h-screen items-center justify-center px-4"
      style={{ backgroundColor: tokens.color.cream, color: tokens.color.ink }}
    >
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className={`${cardClass} w-full max-w-sm space-y-4`}
      >
        <h1 className="text-xl font-light tracking-wide">כניסה לניהול הבוטיק</h1>
        <div>
          <label className={labelClass} htmlFor="login-email">
            אימייל
          </label>
          <input
            id="login-email"
            type="email"
            dir="ltr"
            autoComplete="email"
            required
            className={inputClass}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="login-password">
            סיסמה
          </label>
          <input
            id="login-password"
            type="password"
            dir="ltr"
            autoComplete="current-password"
            required
            className={inputClass}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        {error !== null && <ErrorNotice message={error} />}
        <button type="submit" className={`${primaryButtonClass} w-full`} disabled={busy}>
          כניסה
        </button>
      </form>
    </main>
  );
}
