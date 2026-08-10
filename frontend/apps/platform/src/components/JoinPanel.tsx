import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Button, ButtonLink, Card, Input } from "@boutique/ui";
import { ApiError, api, errorMessage } from "../api";
import type { InvitePreview } from "../api";
import { extractCode } from "../validation";
import markUrl from "../assets/modryn-mark.svg";

// F26 D8 / design Screen B — the ONE screen in this app a non-operator opens,
// and most likely on a phone.
//
// ⚠ NO CONTROL ON THIS SCREEN PASSES `size`. `Button size="sm"` is min-h-9 = 36px
// and fails the 44px touch floor (F-W1); `md` is the component default, so the
// correct call is to pass nothing.

type Step = "code" | "claim" | "done";

// Refusals scoped to the password FIELD go into the Input's `error` slot, where
// they are wired to the control by aria-describedby + aria-invalid. Everything
// else goes to the form-level alert. Getting this wrong is not cosmetic: a
// screen-reader user who cannot associate "too short" with the password box has
// no way to know which of the fields she can see is wrong.
const FIELD_SCOPED = new Set(["empty_password", "password_too_short"]);

export function JoinPanel() {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>("code");
  const [code, setCode] = useState("");
  const [typed, setTyped] = useState("");
  const [invite, setInvite] = useState<InvitePreview | null>(null);
  const [password, setPassword] = useState("");
  const [alert, setAlert] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [spent, setSpent] = useState(false);
  // ⚠ THE SERVER'S `manage_url`, NEVER REBUILT HERE. `join_router.redeem_invite`
  // composes it from `settings.base_domain`, which is `localtest.me` in dev and a
  // deployment's own domain in staging/production. A literal host in this file
  // would be the one actionable link in the feature, wrong everywhere but one.
  const [manageUrl, setManageUrl] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [retry, setRetry] = useState(false);

  // The step's own h2 is the focus target on every transition, so a keyboard or
  // screen-reader user lands on the new content rather than at the top of the
  // document (design §Accessibility).
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, [step]);

  // ⚠ LOOKUP ORDER: platform.join.error.{code} -> platform.error.{code} ->
  // errorMessage(). The join-specific layer exists because the shipped operator
  // sentence for `slug_taken` («הכתובת הזו כבר תפוסה.») tells an owner nothing
  // she can act on — she never chose the address (D2).
  //
  // 429 is matched on STATUS, not on the body's code, following LoginPanel's
  // shipped precedent for the same refusal.
  const refusal = useCallback(
    (error: unknown): string => {
      if (error instanceof ApiError) {
        if (error.status === 429) return t("platform.error.rate_limited");
        for (const key of [`platform.join.error.${error.code}`, `platform.error.${error.code}`]) {
          const sentence = t(key);
          if (sentence !== key) return sentence;
        }
      }
      return errorMessage(error);
    },
    [t],
  );

  const lookup = useCallback(
    async (candidate: string) => {
      setChecking(true);
      setAlert(null);
      setRetry(false);
      try {
        const found = await api.previewInvite(candidate);
        setInvite(found);
        setCode(candidate);
        setStep("claim");
      } catch (error) {
        // Every non-200 lands on the code step with the sentence already in its
        // alert slot. The step is reached BY the failure, so focus arrives with
        // the message and no second announcement is needed.
        setStep("code");
        setInvite(null);
        if (error instanceof ApiError && (error.status === 404 || error.status === 429)) {
          setAlert(refusal(error));
        } else {
          // Network or 5xx: the outage register plus a retry, the house
          // {ns}.loadFailed / {ns}.retry pair.
          setAlert(t("platform.join.loadFailed"));
          setRetry(true);
        }
      } finally {
        setChecking(false);
      }
    },
    [refusal, t],
  );

  // Bootstrap: `#code=` present -> look it up; absent -> the manual code step.
  //
  // ⚠ THE FRAGMENT, NOT THE QUERY STRING. A browser never sends `#…` to the
  // server, so opening the join link writes nothing into uvicorn's access log,
  // the edge proxy's log or a support bundle — which a `?code=` would, for a
  // credential that creates a boutique and stays live for the invite's whole
  // TTL. The link the operator hands over is built to match
  // (`platform/router.py`'s `join_url`).
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.hash.slice(1)).get("code");
    if (fromUrl === null || fromUrl.trim() === "") return;
    void lookup(fromUrl.trim());
    // Once, on mount. The app has no client router, so the fragment cannot
    // change under it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitCode = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const candidate = extractCode(typed);
    if (candidate === "") return;
    void lookup(candidate);
  };

  const submitClaim = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setAlert(null);
    setFieldError(null);
    try {
      const redeemed = await api.redeemInvite(code, password);
      setManageUrl(redeemed.manage_url);
      setPassword("");
      setStep("done");
    } catch (error) {
      if (error instanceof ApiError && FIELD_SCOPED.has(error.code)) {
        setFieldError(refusal(error));
      } else {
        setAlert(refusal(error));
        // ⚠ RACED `invalid_invite` — revoked or redeemed between the preview and
        // this submit. The password is cleared and the form disabled: there is
        // nothing left to retry, and leaving a live password in a dead form
        // invites her to keep pressing.
        if (error instanceof ApiError && error.code === "invalid_invite") {
          setPassword("");
          setSpent(true);
        }
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 py-8 text-ink">
      {/* max-w-md, not LoginPanel's max-w-sm: the claim step renders a <dl> of
          three read-only facts rather than two inputs, and at 384px the
          label-over-value stack wraps at 375. A declared departure from that
          precedent, not a mis-citation. */}
      <div className="w-full max-w-md">
        <h1 className="mb-8 flex flex-col items-center gap-3">
          <img src={markUrl} alt="" width={64} height={64} className="h-16 w-16" />
          <span
            aria-hidden="true"
            dir="ltr"
            className="font-display text-2xl tracking-[0.02em] text-ink"
          >
            MODRYN
          </span>
          <span className="sr-only">{t("platform.join.title")}</span>
        </h1>

        {step === "code" && (
          <Card>
            <form onSubmit={submitCode} className="flex flex-col gap-4">
              <h2
                ref={headingRef}
                tabIndex={-1}
                className="font-display text-xl text-ink outline-none"
              >
                {t("platform.join.headingCode")}
              </h2>
              <Input
                label={t("platform.join.codeLabel")}
                dir="ltr"
                autoComplete="off"
                inputMode="text"
                // Native `required`: a blank submit fires no request and spends
                // no limiter budget.
                required
                value={typed}
                help={t("platform.join.codePrompt")}
                onChange={(event) => setTyped(event.target.value)}
              />
              {alert !== null && (
                <p role="alert" className="text-sm text-danger">
                  {alert}
                </p>
              )}
              {checking && (
                <p role="status" className="text-sm text-ink-muted">
                  {t("platform.join.checking")}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" loading={checking} fullWidthMobile>
                  {t("platform.join.codeSubmit")}
                </Button>
                {retry && (
                  <Button
                    variant="secondary"
                    fullWidthMobile
                    onClick={() => void lookup(extractCode(typed))}
                  >
                    {t("platform.join.retry")}
                  </Button>
                )}
              </div>
            </form>
          </Card>
        )}

        {step === "claim" && invite !== null && (
          <Card>
            <form onSubmit={(event) => void submitClaim(event)} className="flex flex-col gap-4">
              <h2
                ref={headingRef}
                tabIndex={-1}
                className="font-display text-xl text-ink outline-none"
              >
                {t("platform.join.heading")}
              </h2>
              <p className="text-sm text-ink-muted">{t("platform.join.claiming")}</p>
              {/* READ-ONLY, and there is no editable slug or email field anywhere
                  on this screen — that is what makes a leaked link harmless (D2).
                  Bare <bdi> on the boutique NAME (it may be Hebrew); <bdi
                  dir="ltr"> on the address and the email, which are always
                  Latin. */}
              <dl className="grid gap-2 sm:grid-cols-[auto_1fr] sm:gap-x-4">
                <dt className="text-sm font-semibold text-ink">
                  {t("platform.join.boutiqueLabel")}
                </dt>
                <dd className="text-base text-ink">
                  <bdi>{invite.name}</bdi>
                </dd>
                <dt className="text-sm font-semibold text-ink">
                  {t("platform.join.addressLabel")}
                </dt>
                <dd className="text-base text-ink">
                  <bdi dir="ltr">{invite.slug}.modryn.co.il</bdi>
                </dd>
                <dt className="text-sm font-semibold text-ink">{t("platform.join.emailLabel")}</dt>
                <dd className="text-base text-ink">
                  <bdi dir="ltr">{invite.owner_email}</bdi>
                </dd>
              </dl>
              <Input
                label={t("platform.join.password")}
                type="password"
                dir="ltr"
                // new-password, never current-password: the latter offers her an
                // unrelated saved credential for an account that does not exist
                // yet.
                autoComplete="new-password"
                required
                // ⚠ THE FLOOR AS AN ATTRIBUTE, deliberately not an exported
                // constant — `test_frontend_constant_parity` must stay green and
                // a mirrored number is a second definition. The authoritative
                // sentence is the SHIPPED `platform.error.password_too_short`,
                // shown as help BEFORE submit so the failure is prevented rather
                // than reported: the limiter is failures-only at 5/900s, so three
                // typos could lock an owner out of her own boutique for fifteen
                // minutes.
                minLength={10}
                disabled={spent}
                value={password}
                help={t("platform.error.password_too_short")}
                error={fieldError ?? undefined}
                onChange={(event) => setPassword(event.target.value)}
              />
              {alert !== null && (
                <p role="alert" className="text-sm text-danger">
                  {alert}
                </p>
              )}
              <Button type="submit" loading={busy} disabled={spent} fullWidthMobile>
                {t("platform.join.submit")}
              </Button>
            </form>
          </Card>
        )}

        {step === "done" && invite !== null && manageUrl !== null && (
          <Card className="flex flex-col gap-4">
            <h2
              ref={headingRef}
              tabIndex={-1}
              className="font-display text-xl text-ink outline-none"
            >
              {t("platform.join.headingDone")}
            </h2>
            <p role="status" className="text-base text-ink">
              {t("platform.join.success")}
            </p>
            {/* The password is NEVER repeated back. Nothing here mentions
                payments, deposits or gateways: F26 ships no payment code, and
                F17's own banner is the nudge once she turns deposits on (D7). */}
            <p className="text-sm text-ink-muted">
              <Trans
                i18nKey="platform.join.successBody"
                values={{ email: invite.owner_email }}
                components={{ bdi: <bdi dir="ltr" /> }}
              />
            </p>
            {/* The host she reads is PARSED OUT OF the same string the button
                navigates to, so the two can never disagree. */}
            <p className="text-sm text-ink-muted">
              <bdi dir="ltr">{new URL(manageUrl).host}</bdi>
            </p>
            <ButtonLink href={manageUrl} fullWidthMobile>
              {t("platform.join.toManage")}
            </ButtonLink>
          </Card>
        )}
      </div>
    </main>
  );
}
