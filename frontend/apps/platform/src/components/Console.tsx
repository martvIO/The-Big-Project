import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, Input, Modal, Skeleton } from "@boutique/ui";
import { ApiError, api, errorMessage } from "../api";
import type { Operator, Tenant } from "../api";
import { slugProblem } from "../validation";

// Every code the server can refuse a console command with has its own sentence
// (design deck §6); anything else falls through to the API's own message. Keyed
// on `ApiError.code`, never on the message string.
function refusalMessage(error: unknown, t: (key: string) => string): string {
  if (error instanceof ApiError) {
    const key = `platform.error.${error.code}`;
    const sentence = t(key);
    if (sentence !== key) return sentence;
  }
  return errorMessage(error);
}

// `timeZone` is EXPLICIT, not the viewer's default. `created_at` is a UTC
// instant, and an operator reading "when was this boutique opened" is reading it
// in the platform's own frame — a laptop set to another zone would otherwise
// shift the date by a day either side of midnight (the WaitlistSection
// precedent, one app over).
const CREATED = new Intl.DateTimeFormat("he-IL", {
  dateStyle: "medium",
  timeZone: "Asia/Jerusalem",
});

function formatDate(iso: string): string {
  return CREATED.format(new Date(iso));
}

export function Console({ operator, onSignedOut }: { operator: Operator; onSignedOut: () => void }) {
  const { t } = useTranslation();
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [filter, setFilter] = useState("");
  const [rowError, setRowError] = useState<string | null>(null);
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [suspending, setSuspending] = useState<Tenant | null>(null);
  const [resetting, setResetting] = useState<Tenant | null>(null);
  const [resetDone, setResetDone] = useState<string | null>(null);

  // ⚠ FETCHED ONCE PER MOUNT AND NEVER AGAIN. Every GET /platform/tenants writes
  // a TENANTS_LISTED row into platform_audit_log (spec conflict 4 — the one
  // audited read in the product), so the filter is client-side and every mutation
  // patches its row locally. A refetch-after-mutation loop would spam the
  // platform's own book with rows nobody asked for.
  useEffect(() => {
    let cancelled = false;
    api
      .listTenants()
      .then((rows) => {
        if (!cancelled) setTenants(rows);
      })
      .catch(() => {
        if (!cancelled) {
          setTenants([]);
          setLoadFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const patchRow = useCallback((slug: string, changes: Partial<Tenant>) => {
    setTenants((rows) =>
      rows === null ? rows : rows.map((row) => (row.slug === slug ? { ...row, ...changes } : row)),
    );
  }, []);

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      onSignedOut();
    }
  };

  const confirmSuspend = async (tenant: Tenant) => {
    setBusySlug(tenant.slug);
    setRowError(null);
    try {
      await api.suspend(tenant.slug);
      patchRow(tenant.slug, { status: "suspended" });
      setSuspending(null);
    } catch (error) {
      setRowError(refusalMessage(error, t));
      setSuspending(null);
    } finally {
      setBusySlug(null);
    }
  };

  const needle = filter.trim().toLowerCase();
  const visible = (tenants ?? []).filter(
    (row) =>
      needle === "" ||
      row.name.toLowerCase().includes(needle) ||
      row.slug.toLowerCase().includes(needle),
  );

  return (
    <div className="min-h-screen bg-bg text-ink">
      <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="font-display text-2xl text-ink">{t("platform.heading")}</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-ink-muted">
              <bdi>{operator.display_name}</bdi>
            </span>
            <Button variant="ghost" onClick={() => void handleLogout()}>
              {t("platform.logoutCta")}
            </Button>
          </div>
        </header>

        <Card className="flex flex-col gap-4">
          <h2 className="font-display text-xl text-ink">{t("platform.tenants.heading")}</h2>
          <Input
            label={t("platform.tenants.filterLabel")}
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
          {tenants === null ? (
            <Skeleton variant="text" lines={5} />
          ) : loadFailed ? (
            <p role="alert" className="text-sm text-ink-muted">
              {t("platform.tenants.loadFailed")}
            </p>
          ) : tenants.length === 0 ? (
            <EmptyState title={t("platform.tenants.empty")} />
          ) : visible.length === 0 ? (
            <p role="status" className="text-sm text-ink-muted">
              {t("platform.tenants.filterNoMatch")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-start text-sm">
                <caption className="sr-only">{t("platform.tenants.caption")}</caption>
                <thead>
                  <tr className="border-b border-border">
                    <th scope="col" className="py-2 text-start">
                      {t("platform.tenants.colName")}
                    </th>
                    <th scope="col" className="py-2 text-start">
                      {t("platform.tenants.colSlug")}
                    </th>
                    <th scope="col" className="py-2 text-start">
                      {t("platform.tenants.colStatus")}
                    </th>
                    <th scope="col" className="py-2 text-start">
                      {t("platform.tenants.colCreated")}
                    </th>
                    <th scope="col" className="sr-only">
                      {t("platform.tenants.colActions")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row) => {
                    const suspended = row.status === "suspended";
                    return (
                      <tr key={row.slug} className="border-b border-border align-middle">
                        {/* bare <bdi> around the NAME — a Hebrew boutique name
                            must not get dir="ltr" (the BookPage lesson) — and
                            <bdi dir="ltr"> around the slug, which is Latin. */}
                        <td className={`py-3 ${suspended ? "text-ink-muted" : ""}`}>
                          <bdi>{row.name}</bdi>
                        </td>
                        <td className={`py-3 ${suspended ? "text-ink-muted" : ""}`}>
                          <bdi dir="ltr">{row.slug}</bdi>
                        </td>
                        <td className="py-3">
                          {/* The WORD carries the state; colour never does. */}
                          <Badge variant={suspended ? "neutral" : "success"}>
                            {t(
                              suspended
                                ? "platform.tenants.statusSuspended"
                                : "platform.tenants.statusActive",
                            )}
                          </Badge>
                        </td>
                        <td className="py-3">{formatDate(row.created_at)}</td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-2">
                            {/* A suspended boutique loses its suspend action —
                                there is no un-suspend in this console, so the
                                only thing left to do to it is a password reset. */}
                            {!suspended && (
                              <Button
                                variant="secondary"
                                disabled={busySlug === row.slug}
                                onClick={() => {
                                  setRowError(null);
                                  setSuspending(row);
                                }}
                              >
                                {t("platform.tenants.suspendCta")}
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              disabled={busySlug === row.slug}
                              onClick={() => {
                                setRowError(null);
                                setResetDone(null);
                                setResetting(row);
                              }}
                            >
                              {t("platform.tenants.resetCta")}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {rowError !== null && (
            <p role="alert" className="text-sm text-danger">
              {rowError}
            </p>
          )}
          {resetDone !== null && (
            <p role="status" className="text-sm text-ink-muted">
              {resetDone}
            </p>
          )}
        </Card>

        <ProvisionForm
          onProvisioned={(tenant) => setTenants((rows) => [...(rows ?? []), tenant])}
        />
      </div>

      <Modal
        open={suspending !== null}
        onClose={() => setSuspending(null)}
        title={t("platform.suspend.title")}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setSuspending(null)}>
              {t("platform.suspend.cancel")}
            </Button>
            {/* ⚠ THE ONLY `danger` IN THIS FLOW, and the row trigger above is
                deliberately plain. Declared deviation from StaffSection /
                DressEditor, which put danger on the trigger too: at 50+ rows
                that is a column of red buttons and the salience red exists for
                is gone. Table density, not a new house pattern. */}
            <Button
              variant="danger"
              loading={busySlug !== null}
              onClick={() => suspending !== null && void confirmSuspend(suspending)}
            >
              {t("platform.suspend.confirm")}
            </Button>
          </div>
        }
      >
        <p className="text-base text-ink">
          {t("platform.suspend.body", {
            name: suspending?.name ?? "",
            slug: suspending?.slug ?? "",
          })}
        </p>
      </Modal>

      {resetting !== null && (
        <ResetPasswordDialog
          tenant={resetting}
          onClose={() => setResetting(null)}
          onDone={() => {
            setResetting(null);
            setResetDone(t("platform.reset.done"));
          }}
        />
      )}
    </div>
  );
}

function ProvisionForm({ onProvisioned }: { onProvisioned: (tenant: Tenant) => void }) {
  const { t } = useTranslation();
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const problem = slugProblem(slug);
  const slugError =
    problem === "invalid"
      ? t("platform.provision.slugInvalid")
      : problem === "reserved"
        ? t("platform.provision.slugReserved")
        : undefined;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (slugError !== undefined) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      await api.provision({
        slug,
        name,
        owner_email: ownerEmail,
        owner_password: password,
      });
      onProvisioned({
        slug,
        name,
        status: "active",
        // The server echoes nothing back (it would cost a second read of a row
        // the operator is looking at); the row is appended from the values just
        // typed, which is what the design's data discipline calls for.
        created_at: new Date().toISOString(),
      });
      setDone(t("platform.provision.done", { url: `https://${slug}.modryn.co.il` }));
      setSlug("");
      setName("");
      setOwnerEmail("");
      // ⚠ THE PASSWORD LEAVES MEMORY ON SUCCESS and the done-line never repeats
      // it: the console holds no lasting secret, and the operator hands it over
      // out of band.
      setPassword("");
    } catch (provisionError) {
      // Values stay put — a refused slug should not cost the operator the other
      // three fields she typed.
      setError(refusalMessage(provisionError, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
        <h2 className="font-display text-xl text-ink">{t("platform.provision.heading")}</h2>
        <Input
          label={t("platform.provision.slugLabel")}
          dir="ltr"
          required
          value={slug}
          error={slugError}
          help={t("platform.provision.slugHelp", { slug: slug || "…" })}
          onChange={(event) => setSlug(event.target.value)}
        />
        <Input
          label={t("platform.provision.nameLabel")}
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Input
          label={t("platform.provision.ownerEmailLabel")}
          type="email"
          dir="ltr"
          autoComplete="off"
          required
          value={ownerEmail}
          onChange={(event) => setOwnerEmail(event.target.value)}
        />
        <Input
          label={t("platform.provision.ownerPasswordLabel")}
          type="password"
          dir="ltr"
          // ⚠ new-password, NOT current-password: without it the browser offers
          // the OPERATOR's own console credential as the boutique owner's
          // initial password (the manage-staff lesson).
          autoComplete="new-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="text-xs text-ink-muted">{t("platform.provision.passwordNotice")}</p>
        {error !== null && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        {done !== null && (
          <p role="status" className="text-sm text-ink-muted">
            {done}
          </p>
        )}
        <Button type="submit" loading={busy}>
          {t("platform.provision.submitCta")}
        </Button>
      </form>
    </Card>
  );
}

function ResetPasswordDialog({
  tenant,
  onClose,
  onDone,
}: {
  tenant: Tenant;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.resetOwnerPassword(tenant.slug, email, password);
      onDone();
    } catch (resetError) {
      // The modal stays OPEN with both values intact: `owner_not_found` means
      // the address was wrong, and re-typing the password to fix a typo in the
      // email is a punishment for the server's own check.
      setError(refusalMessage(resetError, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={t("platform.reset.title", { name: tenant.name })}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("platform.suspend.cancel")}
          </Button>
          {/* No `danger` anywhere in this dialog — a password reset is not
              destructive, and red here would spend the salience the suspend
              flow needs. */}
          <Button loading={busy} onClick={() => void submit()}>
            {t("platform.reset.submit")}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <Input
          label={t("platform.reset.emailLabel")}
          type="email"
          dir="ltr"
          autoComplete="off"
          help={t("platform.reset.emailHelp")}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input
          label={t("platform.reset.passwordLabel")}
          type="password"
          dir="ltr"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="text-xs text-ink-muted">{t("platform.reset.notice")}</p>
        {error !== null && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
