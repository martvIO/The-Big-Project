import { useEffect, useState } from "react";
import { tokens } from "@boutique/ui";
import { api } from "./api";
import type { Staff } from "./api";
import { HoursSection } from "./components/HoursSection";
import { LoginForm } from "./components/LoginForm";
import { ProfileSection } from "./components/ProfileSection";
import { secondaryButtonClass } from "./components/shared";
import { TermsSection } from "./components/TermsSection";
import { TypesSection } from "./components/TypesSection";

type SectionKey = "profile" | "hours" | "types" | "terms";

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "profile", label: "פרופיל והגדרות" },
  { key: "hours", label: "שעות פעילות" },
  { key: "types", label: "סוגי תורים" },
  { key: "terms", label: "מדיניות ביטולים" },
];

export function App() {
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
      <main
        className="flex min-h-screen items-center justify-center"
        style={{ backgroundColor: tokens.color.cream, color: tokens.color.ink }}
      >
        <p className="text-sm text-stone-500">טוען…</p>
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

  return (
    <main
      className="min-h-screen"
      style={{ backgroundColor: tokens.color.cream, color: tokens.color.ink }}
    >
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4">
          <h1 className="text-xl font-light tracking-wide">ניהול הבוטיק</h1>
          <div className="flex items-center gap-3 text-sm">
            <span style={{ color: tokens.color.gold }}>{staff.display_name}</span>
            <button
              type="button"
              className={secondaryButtonClass}
              onClick={() => void handleLogout()}
            >
              יציאה
            </button>
          </div>
        </div>
      </header>

      <nav className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-4xl gap-1 px-4">
          {SECTIONS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setSection(item.key)}
              className={`border-b-2 px-3 py-2 text-sm ${
                section === item.key
                  ? "border-stone-800 font-medium"
                  : "border-transparent text-stone-500"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </nav>

      <div className="mx-auto max-w-4xl px-4 py-6">
        {section === "profile" && <ProfileSection />}
        {section === "hours" && <HoursSection />}
        {section === "types" && <TypesSection />}
        {section === "terms" && <TermsSection />}
      </div>
    </main>
  );
}
