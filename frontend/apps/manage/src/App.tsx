import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ConsoleShell, ToastProvider } from "@boutique/ui";
import { api } from "./api";
import type { Staff } from "./api";
import { BookingsSection } from "./components/BookingsSection";
import { CatalogSection } from "./components/CatalogSection";
import { GatewaySection } from "./components/GatewaySection";
import { HoursSection } from "./components/HoursSection";
import { LoginForm } from "./components/LoginForm";
import { ProfileSection } from "./components/ProfileSection";
import { StaffSection } from "./components/StaffSection";
import { TermsSection } from "./components/TermsSection";
import { TypesSection } from "./components/TypesSection";

type SectionKey =
  | "profile"
  | "hours"
  | "types"
  | "terms"
  | "catalog"
  | "bookings"
  | "staff"
  | "gateway";

const ALL = ["owner", "shift_manager"] as const;

// The console's single permission-to-UI table.
//
// **This is COSMETICS.** The control is the server's RoleGate, which refuses a
// shift manager on every /manage/staff route with a 403; the filter exists only
// so she is not shown a door that answers one. Both sentences live here because
// the failure mode of forgetting them is someone later "simplifying" the server
// gate away on the strength of this array.
// `roles: readonly string[]`, not the literal tuple `as const` would infer:
// staff.role is whatever staff_users.role held, and `["owner"].includes(x)`
// refuses to take a plain string.
interface NavItem {
  key: SectionKey;
  labelKey: string;
  roles: readonly string[];
}

const NAV: readonly NavItem[] = [
  { key: "profile", labelKey: "nav.profile", roles: ALL },
  { key: "hours", labelKey: "nav.hours", roles: ALL },
  { key: "types", labelKey: "nav.types", roles: ALL },
  { key: "terms", labelKey: "nav.terms", roles: ALL },
  { key: "catalog", labelKey: "nav.catalog", roles: ALL },
  { key: "bookings", labelKey: "nav.bookings", roles: ALL },
  { key: "staff", labelKey: "nav.staff", roles: ["owner"] },
  // Owner-only, the READ included: /manage/gateway is the first backend router
  // that is owner-only in full, and whether the boutique can take money is
  // itself disclosure.
  { key: "gateway", labelKey: "nav.gateway", roles: ["owner"] },
];

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

  const reachable = NAV.filter((item) => item.roles.includes(staff.role));
  // Derived at render, never stored. Nothing persists `section` — but
  // handleLogout clears `staff` and not `section`, so an owner sitting on «צוות»
  // who logs out and hands the front-desk browser to a shift manager would leave
  // her on a panel her role cannot reach. Two lines that cannot go stale, and
  // they also cover a mid-session role change if a later feature adds one.
  //
  // `reachable[0]?.key ?? section` rather than `reachable[0].key`: a role the
  // enum does not know reaches NO row, and GET /manage/auth/me echoes
  // staff_users.role verbatim with no allowlist (pinned by
  // test_me_echoes_an_out_of_enum_role_verbatim). 0011's CHECK is what makes
  // such a row impossible in the database — but "impossible state white-screens
  // the console" is a worse failure than an empty nav, and the `?.` is one
  // character.
  const activeKey = reachable.some((item) => item.key === section)
    ? section
    : (reachable[0]?.key ?? section);
  const nav = reachable.map((item) => ({ key: item.key, label: t(item.labelKey) }));

  return (
    <ToastProvider>
      <ConsoleShell
        boutiqueName={staff.display_name}
        title={t("console.title")}
        logoutLabel={t("console.logout")}
        onLogout={() => void handleLogout()}
        skipLinkLabel={t("console.skipLink")}
        nav={nav}
        activeKey={activeKey}
        onNavigate={(key) => setSection(key as SectionKey)}
      >
        {activeKey === "profile" && <ProfileSection />}
        {activeKey === "hours" && <HoursSection />}
        {activeKey === "types" && <TypesSection />}
        {activeKey === "terms" && <TermsSection role={staff.role} />}
        {activeKey === "catalog" && <CatalogSection />}
        {activeKey === "bookings" && <BookingsSection />}
        {activeKey === "staff" && <StaffSection staffId={staff.id} />}
        {activeKey === "gateway" && <GatewaySection />}
      </ConsoleShell>
    </ToastProvider>
  );
}
