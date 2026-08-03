import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ConsoleShell, ToastProvider } from "@boutique/ui";
import { api } from "./api";
import type { Staff } from "./api";
import { AtelierSection } from "./components/AtelierSection";
import { BoardSection } from "./components/BoardSection";
import { BookingsSection } from "./components/BookingsSection";
import { CatalogSection } from "./components/CatalogSection";
import { CheckinQrSection } from "./components/CheckinQrSection";
import { CustomersSection } from "./components/CustomersSection";
import { DashboardSection } from "./components/DashboardSection";
import { GatewaySection } from "./components/GatewaySection";
import { HoursSection } from "./components/HoursSection";
import { LoginForm } from "./components/LoginForm";
import { ProfileSection } from "./components/ProfileSection";
import { SosOverlay } from "./components/SosOverlay";
import { StaffSection } from "./components/StaffSection";
import { TermsSection } from "./components/TermsSection";
import { SosProvider } from "./lib/sos";
import { FloorPanel } from "./components/FloorPanel";
import { TypesSection } from "./components/TypesSection";

type SectionKey =
  | "dashboard"
  | "profile"
  | "hours"
  | "types"
  | "terms"
  | "catalog"
  | "bookings"
  | "customers"
  | "board"
  | "staff"
  | "gateway"
  // F57's floor — the TWELFTH member since F53 added `customers`.
  | "floor"
  // F33's printable check-in code — the THIRTEENTH.
  | "checkinQr"
  // F41's atelier — the FOURTEENTH.
  | "atelier";

const ALL = ["owner", "shift_manager"] as const;

// F57's three. They reach exactly one nav row and exactly one section.
//
// ⚠ Declined: widening `board`'s roles to all five instead of adding a row. A
// seamstress would land on a section labelled «לוח היום» whose board the server
// refuses her, BoardSection's first fetch would 403, and its own terminalOf
// correctly treats that as terminal — blanking the screen. The label would
// promise a thing the gate forbids and the component would be right to break.
// Nav.test.tsx's count assertions (owner ten, shift manager eight) are what make
// this a test rather than a preference.
const FLOOR_ONLY = ["reception", "sales_assistant", "seamstress"] as const;

// F41's three, and the three are SPELLED rather than derived. A receptionist and
// a sales assistant have no business in the workroom, and a sixth role added
// later must be refused here BY DEFAULT — spelling them is what makes that the
// safe direction to fail. It mirrors the atelier router, which spells the same
// three as literals for the same reason.
//
// `FLOOR_ONLY` is UNCHANGED: a seamstress now reaches TWO rows, and because the
// atelier row sits after `floor`, `reachable[0]?.key ?? section` still lands her
// on the floor with no edit to useState("dashboard") below.
const ATELIER_ROLES = ["owner", "shift_manager", "seamstress"] as const;

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
  // FIRST, and reachable by both roles: the console lands here (D10), so this
  // row's position is what makes the initial `section` below and the
  // `reachable[0]` fallback agree.
  { key: "dashboard", labelKey: "nav.dashboard", roles: ALL },
  { key: "profile", labelKey: "nav.profile", roles: ALL },
  { key: "hours", labelKey: "nav.hours", roles: ALL },
  { key: "types", labelKey: "nav.types", roles: ALL },
  { key: "terms", labelKey: "nav.terms", roles: ALL },
  { key: "catalog", labelKey: "nav.catalog", roles: ALL },
  { key: "bookings", labelKey: "nav.bookings", roles: ALL },
  // Immediately after «תורים»: a customer card is where a row in that list
  // leads, and the front desk reads the two together. `roles: ALL` because the
  // server admits a shift manager on every /manage/customers route — a hidden
  // door here would be this array lying about the API rather than mirroring it.
  //
  // ⚠ A RECORDED DEPARTURE from spec D10 and the plan, which both place this row
  // "after `board`, before `staff`". Taken deliberately, not by accident: D10
  // was written before F57 merged, when `board` was the last both-roles row, so
  // "after board" and "adjacent to the work" were the same position. They no
  // longer are — `floor` now sits between `board` and `staff`, so obeying D10
  // literally would put «לקוחות» after a row that only reception, sales
  // assistants and seamstresses can see, splitting the two lists the front desk
  // reads together. Position is the only thing at stake; nothing behavioural
  // depends on it.
  { key: "customers", labelKey: "nav.customers", roles: ALL },
  // The board sits AFTER «תורים» and not at the top, which is what keeps Q-5 =
  // NO true structurally: the landing section is row 0 above, and nothing
  // inserted below it can displace either the initial `section` or the
  // `reachable[0]` fallback. `roles: ALL` because a board a shift manager
  // cannot open is not a shift manager's board (spec D5) — and, as the note
  // above says, this array is cosmetics: the control is the server's RoleGate,
  // which is also why the board treats a 403 as terminal.
  { key: "board", labelKey: "nav.board", roles: ALL },
  // Immediately after the board, and ONLY for the three floor roles: the owner
  // and the shift manager reach the same panel under «לוח היום» (Task 11 renders
  // it beneath the board there) and get no second row. For the three, this is
  // the only row they will ever see, so `reachable[0]?.key ?? section` lands
  // them here with no edit to the initial useState("dashboard").
  { key: "floor", labelKey: "nav.floor", roles: FLOOR_ONLY },
  // F41, IMMEDIATELY AFTER `floor` — and that is the SAME SLOT as "after «לוח
  // היום», before «צוות»", which is how the spec phrases it. The two phrasings
  // are not in conflict and neither may be "fixed" against the other: `floor`
  // carries FLOOR_ONLY, so the owner never sees it and «תפירה» is adjacent to
  // «לוח היום» in HER list.
  //
  // Put it BEFORE `floor` instead and two things break together: a seamstress's
  // rows come out «תפירה» then «הצוות בקומה», and `reachable[0]?.key` lands her
  // on the atelier instead of the floor. One line, three consequences —
  // Nav.test.tsx's seamstress ORDER assertion is what makes that a test.
  { key: "atelier", labelKey: "nav.atelier", roles: ATELIER_ROLES },
  // F33, and `roles: ALL` is a decision rather than a default — it mirrors the
  // server, which admits both console roles to GET /manage/checkin-qr. The
  // payload is a public URL and a picture of it, the same URL printed on a sign
  // in the window that anyone in the shop can read, so the disclosure is zero
  // and locking a shift manager out of reprinting a torn poster is a support
  // ticket for no security gain.
  //
  // Placed after `floor` and before `staff`: the `floor` row is invisible to
  // both roles that can see this one, so this is the ELEVENTH row either of them
  // sees since F41's atelier went in above it (Nav.test.tsx's `.slice(0, 11)`)
  // while leaving F57's "immediately after the board" true for the three floor
  // roles. The two owner-only rows stay structurally last.
  { key: "checkinQr", labelKey: "nav.checkinQr", roles: ALL },
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
  // The landing section. Was "profile" — the screen an owner configures once
  // and never opens again, shown to her and to every shift manager on every
  // login. An out-of-enum role reaches no NAV row at all, so the fallback below
  // now lands it here rather than on a 200-ing Profile panel, and its one fetch
  // 403s — which is why DashboardSection's outage copy covers any ApiError.
  const [section, setSection] = useState<SectionKey>("dashboard");

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
      {/* ⚠ A PROVIDER, MOUNTED HERE, AND THE FORCING CONSTRAINT IS MECHANICAL:
          this component early-returns for `!bootstrapped` and again for a
          signed-out staffer, so a hook called after those returns is a
          rules-of-hooks violation — a LINT failure rather than a runtime one. A
          provider is a component boundary, so it may be mounted conditionally
          where a hook may not. `ToastProvider` is the shipped precedent and is
          already wrapped around this same tree.

          ⚠ `onSessionEnded` HANGS OFF THE PROVIDER AND NOT OFF THE OVERLAY. The
          401 is classified at ONE site — inside the provider, where the read and
          the four actions all funnel — so it fires exactly once. On the overlay
          it would have a second firing site and no way to agree with the first.
          `setStaff(null)` is the only thing in this console that drops it to the
          login form: there is no fetch interceptor and `onNavigate` is
          `setSection`, so without this callback the console would keep rendering
          a working-looking shell over a dead emergency channel, on eleven
          sections that poll nothing else. */}
      <SosProvider onSessionEnded={() => setStaff(null)}>
        {/* BEFORE the shell, so the overlay's controls precede every other
            focusable in DOM order — and so the Esc route-in reaches the ack
            control without walking the whole console chrome first. */}
        <SosOverlay />
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
          {activeKey === "dashboard" && <DashboardSection />}
          {activeKey === "profile" && <ProfileSection />}
          {activeKey === "hours" && <HoursSection />}
          {activeKey === "types" && <TypesSection />}
          {activeKey === "terms" && <TermsSection role={staff.role} />}
          {activeKey === "catalog" && <CatalogSection />}
          {activeKey === "bookings" && <BookingsSection />}
          {activeKey === "customers" && <CustomersSection />}
          {/* The panel goes AFTER the board, never before: above it, the panel
              grows as breaks start and pushes the board's one-shot scrollIntoView
              target — the «עכשיו» divider — back out of view. */}
          {activeKey === "board" && (
            <div className="space-y-6">
              <BoardSection />
              <FloorPanel selfId={staff.id} role={staff.role} />
            </div>
          )}
          {activeKey === "floor" && <FloorPanel selfId={staff.id} role={staff.role} />}
          {/* ALONE in #console-main and never beneath another section: it owns its
              own usePoll instance, and the console renders one section at a time
              precisely so a workroom phone is not running two loops. */}
          {activeKey === "atelier" && <AtelierSection selfId={staff.id} role={staff.role} />}
          {activeKey === "checkinQr" && <CheckinQrSection />}
          {activeKey === "staff" && <StaffSection staffId={staff.id} />}
          {activeKey === "gateway" && <GatewaySection />}
        </ConsoleShell>
      </SosProvider>
    </ToastProvider>
  );
}
