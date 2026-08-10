import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, Input, Modal, Skeleton } from "@boutique/ui";
import { ApiError, api, errorMessage } from "../api";
import type { Invite, InviteCreated, Operator, Tenant } from "../api";
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

// ⚠ TO THE MINUTE, unlike `CREATED` above. An expiry stated to the day only is a
// lie about when the link dies — the operator hands this over and the owner acts
// on it, so «בתוקף עד 12 באוגוסט» reads as "any time that day" when the real
// instant is 09:04. Same explicit Jerusalem frame, same reason.
const EXPIRES = new Intl.DateTimeFormat("he-IL", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Jerusalem",
});

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
          baseDomain={operator.base_domain}
          onProvisioned={(tenant) => setTenants((rows) => [...(rows ?? []), tenant])}
        />

        <InvitesSection baseDomain={operator.base_domain} />
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

function ProvisionForm({
  baseDomain,
  onProvisioned,
}: {
  baseDomain: string;
  onProvisioned: (tenant: Tenant) => void;
}) {
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
      setDone(t("platform.provision.done", { url: `https://${slug}.${baseDomain}` }));
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
      {/* ⚠ NAMED, because F26's create-invite form reuses these exact three
          labels (design A1's declared deviation: the fields are byte-identical,
          and three duplicate strings would be a drift surface). Two same-named
          controls on one page is only ambiguous if neither form is addressable —
          `aria-labelledby` makes each one a landmark of its own for a screen
          reader and for a test. */}
      <form
        aria-labelledby="provision-heading"
        onSubmit={(event) => void handleSubmit(event)}
        className="flex flex-col gap-4"
      >
        <h2 id="provision-heading" className="font-display text-xl text-ink">
          {t("platform.provision.heading")}
        </h2>
        <Input
          label={t("platform.provision.slugLabel")}
          dir="ltr"
          required
          value={slug}
          error={slugError}
          help={t("platform.provision.slugHelp", { slug: slug || "…", domain: baseDomain })}
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

// F26 design Screens A1–A4. Two Cards and one Modal, beside F25's tenants table
// and provision form.
//
// ⚠ NO CALL SITE BELOW PASSES `size` (F-W1: `sm` is min-h-9 = 36px, under the
// 44px floor), and the ONLY `danger` is the revoke Modal's footer confirm — the
// row trigger is plain, F25's suspend precedent for table density.
function InvitesSection({ baseDomain }: { baseDomain: string }) {
  const { t } = useTranslation();
  const [invites, setInvites] = useState<Invite[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<Invite | null>(null);
  // ⚠ A2 RULE 7: THE RAW CODE LIVES IN EXACTLY ONE REACT STATE VARIABLE.
  // Not in `location`, not in sessionStorage or localStorage, not in a data-*
  // attribute, not in the document title, not in a console.log. A reload, a
  // re-login or any remount loses it — and `GET /platform/invites` never returns
  // it (D6), so the table below cannot re-render it either.
  const [created, setCreated] = useState<InviteCreated | null>(null);

  // Fetched once per mount, like the tenants table. The reason differs — this
  // GET writes no audit row — but a refetch after a mutation would blank the
  // table under the operator for nothing, so create appends and revoke removes
  // locally.
  useEffect(() => {
    let cancelled = false;
    api
      .listInvites()
      .then((rows) => {
        if (!cancelled) setInvites(rows);
      })
      .catch(() => {
        if (!cancelled) {
          setInvites([]);
          setLoadFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const confirmRevoke = async (invite: Invite) => {
    setBusyId(invite.id);
    setRowError(null);
    try {
      await api.revokeInvite(invite.id);
      setInvites((rows) => (rows === null ? rows : rows.filter((row) => row.id !== invite.id)));
      setRevoking(null);
    } catch (error) {
      setRowError(refusalMessage(error, t));
      setRevoking(null);
    } finally {
      setBusyId(null);
    }
  };

  const now = Date.now();

  return (
    <>
      <Card className="flex flex-col gap-4">
        <h2 className="font-display text-xl text-ink">{t("platform.invites.heading")}</h2>
        {invites === null ? (
          <Skeleton variant="text" lines={4} />
        ) : loadFailed ? (
          <p role="alert" className="text-sm text-ink-muted">
            {t("platform.invites.loadFailed")}
          </p>
        ) : invites.length === 0 ? (
          <EmptyState title={t("platform.invites.empty")} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-start text-sm">
              <caption className="sr-only">{t("platform.invites.caption")}</caption>
              <thead>
                <tr className="border-b border-border">
                  <th scope="col" className="py-2 text-start">
                    {t("platform.invites.colName")}
                  </th>
                  <th scope="col" className="py-2 text-start">
                    {t("platform.invites.colSlug")}
                  </th>
                  <th scope="col" className="py-2 text-start">
                    {t("platform.invites.colOwnerEmail")}
                  </th>
                  <th scope="col" className="py-2 text-start">
                    {t("platform.invites.colStatus")}
                  </th>
                  <th scope="col" className="py-2 text-start">
                    {t("platform.invites.colExpires")}
                  </th>
                  {/* NO CODE COLUMN EXISTS (A2 r7) — the wire type has no such
                      field, and this is the screen where one would be rendered. */}
                  <th scope="col" className="sr-only">
                    {t("platform.invites.colActions")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {invites.map((row) => {
                  const redeemed = row.redeemed_at !== null;
                  // Derived client-side: the server has no "expired" state, only
                  // an instant, and a row that expires while the console is open
                  // must not keep offering an action that will refuse.
                  const expired = !redeemed && new Date(row.expires_at).getTime() <= now;
                  const open = !redeemed && !expired;
                  return (
                    <tr key={row.id} className="border-b border-border align-middle">
                      <td className={`py-3 ${open ? "" : "text-ink-muted"}`}>
                        <bdi>{row.name}</bdi>
                      </td>
                      <td className={`py-3 ${open ? "" : "text-ink-muted"}`}>
                        <bdi dir="ltr">{row.slug}</bdi>
                      </td>
                      <td className={`py-3 ${open ? "" : "text-ink-muted"}`}>
                        <bdi dir="ltr">{row.owner_email}</bdi>
                      </td>
                      <td className="py-3">
                        {/* The WORD carries the state; colour never does, and the
                            expired row's muted text is redundant with its word. */}
                        <Badge variant={open ? "success" : "neutral"}>
                          {t(
                            redeemed
                              ? "platform.invites.statusRedeemed"
                              : expired
                                ? "platform.invites.statusExpired"
                                : "platform.invites.statusOpen",
                          )}
                        </Badge>
                      </td>
                      <td className="py-3">{EXPIRES.format(new Date(row.expires_at))}</td>
                      <td className="py-3">
                        {/* Only an OPEN row carries the action. There is nothing
                            left to do to a redeemed or expired invite. */}
                        {open && (
                          <Button
                            variant="secondary"
                            disabled={busyId === row.id}
                            onClick={() => {
                              setRowError(null);
                              setRevoking(row);
                            }}
                          >
                            {t("platform.invites.revokeCta")}
                          </Button>
                        )}
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
      </Card>

      <CreateInviteCard
        baseDomain={baseDomain}
        created={created}
        onCreated={(result) => {
          setCreated(result);
          setInvites((rows) => [result.invite, ...(rows ?? [])]);
        }}
        onDismiss={() => setCreated(null)}
      />

      <Modal
        open={revoking !== null}
        onClose={() => setRevoking(null)}
        title={t("platform.invites.revokeTitle")}
        footer={
          <div className="flex justify-end gap-2">
            {/* «חזרה», NOT «ביטול» (design A4): a dialog whose confirm reads
                «ביטול ההזמנה» beside a cancel reading «ביטול» is a mis-click
                generator. F25's platform.suspend.cancel is untouched. */}
            <Button variant="secondary" onClick={() => setRevoking(null)}>
              {t("platform.invites.revokeCancel")}
            </Button>
            <Button
              variant="danger"
              loading={busyId !== null}
              onClick={() => revoking !== null && void confirmRevoke(revoking)}
            >
              {t("platform.invites.revokeConfirm")}
            </Button>
          </div>
        }
      >
        <p className="text-base text-ink">
          <Trans
            i18nKey="platform.invites.revokeBody"
            values={{ name: revoking?.name ?? "", slug: revoking?.slug ?? "" }}
            // ⚠ Trans, not t(): the slug must land inside a <bdi dir="ltr"> and
            // the boutique name inside a BARE <bdi> (it may be Hebrew — the
            // BookPage lesson). The parentheses in this sentence are exactly the
            // neutral characters that reorder without an isolate. Do not
            // "simplify" this back to t() (StaffSection.tsx:443-454's note).
            components={{ bdi: <bdi dir="ltr" />, name: <bdi /> }}
          />
        </p>
      </Modal>
    </>
  );
}

// A2. The create form and the one-time link panel are MUTUALLY EXCLUSIVE inside
// one Card (rule 3): a second create cannot clobber an unread code, and the
// panel cannot scroll out of sight behind a form the operator is retyping into.
function CreateInviteCard({
  baseDomain,
  created,
  onCreated,
  onDismiss,
}: {
  baseDomain: string;
  created: InviteCreated | null;
  onCreated: (result: InviteCreated) => void;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<"ok" | "failed" | null>(null);
  const slugRef = useRef<HTMLInputElement>(null);

  const problem = slugProblem(slug);
  // The SHIPPED provision keys, reused rather than duplicated (design A1's
  // declared deviation from spec D8): the three fields are byte-identical to the
  // provision form's, and three duplicate strings are a drift surface for zero
  // benefit.
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
    try {
      const result = await api.createInvite({ slug, name, owner_email: ownerEmail });
      // Cleared BEHIND the panel: the form is not rendered while it is open, and
      // dismissing it must return an empty one.
      setSlug("");
      setName("");
      setOwnerEmail("");
      setCopied(null);
      onCreated(result);
    } catch (createError) {
      // Values stay put — a refused slug should not cost the operator the other
      // two fields she typed.
      setError(refusalMessage(createError, t));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(created?.join_url ?? "");
      setCopied("ok");
    } catch {
      // No navigator.clipboard, or an insecure origin. The manual path is stated
      // rather than left to be discovered, and the link Input stays selectable
      // (readOnly, never disabled) so it is actually available.
      setCopied("failed");
    }
  };

  if (created !== null) {
    return (
      <Card className="flex flex-col gap-4">
        {/* A PANEL INSIDE THE CARD, NEVER A Modal (A2 r1): Modal is a native
            <dialog> wired to close on Esc, which is one accidental keypress away
            from losing the only copy of a credential. This has no dismissal
            vector at all — no Esc, no backdrop, no timeout, no ✕. */}
        <h3 className="font-display text-lg text-ink">{t("platform.invites.createdHeading")}</h3>
        <p className="text-sm text-ink">
          <Trans
            i18nKey="platform.invites.createdFor"
            values={{ name: created.invite.name, url: `${created.invite.slug}.${baseDomain}` }}
            components={{ bdi: <bdi dir="ltr" />, name: <bdi /> }}
          />
        </p>
        <p className="text-sm text-ink">{t("platform.invites.linkOnce")}</p>
        {/* readOnly, NOT disabled (A2 r4): a disabled control is unfocusable and
            unselectable, so manual copy would be impossible on exactly the
            machine where the clipboard API is unavailable. An <input> scrolls and
            never truncates, so no character hides behind an ellipsis.
            NEVER an <a href> and no "open link" control (r5): a click would put a
            live code in browser history and in a referrer. */}
        <Input
          label={t("platform.invites.linkLabel")}
          dir="ltr"
          readOnly
          value={created.join_url}
          onFocus={(event) => event.target.select()}
        />
        <p className="text-sm text-ink-muted">
          {t("platform.invites.linkExpires", {
            date: EXPIRES.format(new Date(created.invite.expires_at)),
          })}
        </p>
        <p className="text-sm text-ink-muted">{t("platform.invites.linkDeliver")}</p>
        {copied === "ok" && (
          <p role="status" className="text-sm text-ink-muted">
            {t("platform.invites.copied")}
          </p>
        )}
        {copied === "failed" && (
          <p role="alert" className="text-sm text-danger">
            {t("platform.invites.copyFailed")}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button fullWidthMobile onClick={() => void copy()}>
            {t("platform.invites.copy")}
          </Button>
          {/* ⚠ LAST IN DOM ORDER, deliberately: a thumb reaching the bottom of
              the panel must not land on the dismiss before the copy. Its label
              states the consequence (r2) — there is no bare ✕ anywhere here. */}
          <Button
            variant="secondary"
            fullWidthMobile
            onClick={() => {
              setCopied(null);
              onDismiss();
              // Focus moves to the field she will type into next, so the panel's
              // unmount does not drop a keyboard user at the top of the document.
              window.requestAnimationFrame(() => slugRef.current?.focus());
            }}
          >
            {t("platform.invites.dismiss")}
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <form
        aria-labelledby="create-invite-heading"
        onSubmit={(event) => void handleSubmit(event)}
        className="flex flex-col gap-4"
      >
        <h2 id="create-invite-heading" className="font-display text-xl text-ink">
          {t("platform.invites.createHeading")}
        </h2>
        <Input
          ref={slugRef}
          label={t("platform.provision.slugLabel")}
          dir="ltr"
          required
          value={slug}
          error={slugError}
          help={t("platform.provision.slugHelp", { slug: slug || "…", domain: baseDomain })}
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
        {/* NO PASSWORD FIELD — that is the whole feature (D2). And no expiry
            statement before submit: the TTL is a server setting, and mirroring it
            here would be a second definition of it. */}
        {error !== null && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Button type="submit" loading={busy}>
          {t("platform.invites.createCta")}
        </Button>
      </form>
    </Card>
  );
}
