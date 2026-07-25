import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ConsoleShell } from "@boutique/ui";
import { api } from "./api";
import type { Staff } from "./api";
import { CatalogSection } from "./components/CatalogSection";
import { HoursSection } from "./components/HoursSection";
import { LoginForm } from "./components/LoginForm";
import { ProfileSection } from "./components/ProfileSection";
import { TermsSection } from "./components/TermsSection";
import { TypesSection } from "./components/TypesSection";

type SectionKey = "profile" | "hours" | "types" | "terms" | "catalog";

export function App() {
  const { t } = useTranslation();
  const [staff, setStaff] = useState<Staff | null>(null);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [section, setSection] = useState<SectionKey>("profile");

  useEffect(() => {
    api
      .me()
      .then(setStaff)
      .catch(() => setStaff(null))
      .finally(() => setBootstrapped(true));
  }, []);

  if (!bootstrapped) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg text-ink">
        <p className="text-base text-ink-muted">{t("console.loading")}</p>
      </main>
    );
  }

  if (staff === null) {
    return <LoginForm onLogin={setStaff} />;
  }

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {
      // The session may already be gone server-side — drop it locally anyway.
    }
    setStaff(null);
  };

  const nav = [
    { key: "profile", label: t("nav.profile") },
    { key: "hours", label: t("nav.hours") },
    { key: "types", label: t("nav.types") },
    { key: "terms", label: t("nav.terms") },
    { key: "catalog", label: t("nav.catalog") },
  ];

  return (
    <ConsoleShell
      boutiqueName={staff.display_name}
      title={t("console.title")}
      logoutLabel={t("console.logout")}
      onLogout={() => void handleLogout()}
      skipLinkLabel={t("console.skipLink")}
      nav={nav}
      activeKey={section}
      onNavigate={(key) => setSection(key as SectionKey)}
    >
      {section === "profile" && <ProfileSection />}
      {section === "hours" && <HoursSection />}
      {section === "types" && <TypesSection />}
      {section === "terms" && <TermsSection />}
      {section === "catalog" && <CatalogSection />}
    </ConsoleShell>
  );
}
