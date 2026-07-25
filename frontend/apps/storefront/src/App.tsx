import { useTranslation } from "react-i18next";

export function App() {
  const { t } = useTranslation();
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 text-ink">
      <div className="text-center">
        <h1 className="font-display text-3xl text-ink">{t("placeholder.heading")}</h1>
        <p className="mt-2 text-base text-ink-muted">{t("placeholder.body")}</p>
      </div>
    </main>
  );
}
