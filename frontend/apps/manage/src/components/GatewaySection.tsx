import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, Input, PolicyBlockerBanner, SectionHeading, Skeleton } from "@boutique/ui";
import { ApiError, api, errorMessage } from "../api";
import type { GatewayStatus } from "../api";
import { jerusalemDate, jerusalemTime } from "../lib/jerusalem";

// The codes this section renders its OWN Hebrew for. Everything else — including
// VALIDATION_ERROR, whose message is the server's own field-name text — falls
// through to errorMessage(). Kept by hand and not pinned by anything, exactly
// like StaffSection's MAPPED_CODES.
const MAPPED_CODES = new Set([
  "GATEWAY_CREDENTIALS_REJECTED",
  "GATEWAY_NOT_CONFIGURED",
  "GATEWAY_NOT_CONNECTED",
  "GATEWAY_UNAVAILABLE",
  "TOO_MANY_ATTEMPTS",
]);

// The provider literal that means "records, never charges". Staging runs it with
// the fake secret box, so a real merchant credential typed into this form would
// be stored as base64 of plaintext — both production boot guards key on
// APP_ENV=production only, and migration 0012's CHECK admits 'fake' everywhere.
const TEST_PROVIDER = "fake";

export function GatewaySection() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<GatewayStatus | null>(null);
  // Composed from the two calls the console ALREADY makes, rather than a derived
  // field on the gateway API: "deposits are on with nothing behind them" is a
  // cross-section fact, and putting it on GatewayStatus would make the payments
  // service read tenants.settings for a banner. Fetched here rather than passed
  // down so App.tsx stays a three-line diff while sibling features land in it.
  const [depositsEnabled, setDepositsEnabled] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Always EMPTY on load, and re-emptied after every save. Credentials are
  // write-only by construction — the API has no read path for a field value —
  // so there is nothing to prefill and a save always sends the complete set.
  const [values, setValues] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Two-step reveal-then-confirm, the F16 cancel precedent: disconnecting stops
  // deposits for the WHOLE boutique.
  const [confirmingDisconnect, setConfirmingDisconnect] = useState(false);

  const load = useCallback(async () => {
    try {
      const [gateway, settings] = await Promise.all([api.gatewayStatus(), api.getSettings()]);
      setStatus(gateway);
      setDepositsEnabled(settings.toggles.deposits_enabled ?? false);
      setLoadError(null);
    } catch (error) {
      setStatus(null);
      setLoadError(errorMessage(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const describe = (error: unknown): string => {
    if (error instanceof ApiError && MAPPED_CODES.has(error.code)) {
      return t(`gateway.error.${error.code}`);
    }
    return errorMessage(error);
  };

  const run = async (call: () => Promise<GatewayStatus>, onDone?: () => void) => {
    setBusy(true);
    try {
      setStatus(await call());
      setFormError(null);
      onDone?.();
    } catch (error) {
      setFormError(describe(error));
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (status === null) {
      return;
    }
    // The complete set, every time. No client-side shape check: the server owns
    // the adapter's declared field list and its 400 is the only authority — a
    // second copy here could refuse a set the adapter would have accepted.
    const fields = Object.fromEntries(
      status.credential_fields.map((field) => [field, values[field] ?? ""]),
    );
    void run(
      () => api.setGatewayCredentials(fields),
      () => setValues({}),
    );
  };

  if (loadError !== null) {
    return (
      <p role="alert" className="text-sm text-ink-muted">
        {loadError}
      </p>
    );
  }
  if (status === null) {
    return <Skeleton variant="text" lines={4} />;
  }

  // PLATFORM has no adapter: an explanatory line, no form, no buttons. Nothing
  // here is the owner's to fix, and a form would imply otherwise.
  if (!status.configured) {
    return (
      <Card>
        <SectionHeading>{t("gateway.heading")}</SectionHeading>
        <p className="mt-2 text-base text-ink">{t("gateway.notConfigured")}</p>
        <p className="mt-1 text-sm text-ink-muted">{t("gateway.notConfiguredHelp")}</p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {depositsEnabled && !status.connected && (
        <PolicyBlockerBanner
          message={t("gateway.depositsWithoutGateway")}
          actionLabel={t("gateway.depositsWithoutGatewayCta")}
          onAction={() => {
            document.getElementById("gateway-credentials-form")?.scrollIntoView();
          }}
        />
      )}

      <Card>
        <SectionHeading>{t("gateway.heading")}</SectionHeading>
        <p className="mt-2 flex items-center gap-2 text-base text-ink">
          {status.connected ? t("gateway.connected") : t("gateway.notConnected")}
          {status.status !== null && (
            <Badge variant={status.status === "valid" ? "success" : "danger"}>
              {status.status === "valid" ? t("gateway.statusValid") : t("gateway.statusInvalid")}
            </Badge>
          )}
        </p>
        {status.last_validated_at !== null && (
          <p className="mt-1 text-sm text-ink-muted">
            {t("gateway.lastValidated")}{" "}
            {/* The instant is an LTR run inside RTL Hebrew — isolate it (R19). */}
            <bdi dir="ltr">
              {jerusalemDate(status.last_validated_at)} {jerusalemTime(status.last_validated_at)}
            </bdi>
          </p>
        )}
        {status.connected && (
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="secondary" disabled={busy} onClick={() => void run(api.validateGateway)}>
              {t("gateway.validateCta")}
            </Button>
            {confirmingDisconnect ? (
              <>
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void run(api.disconnectGateway, () => setConfirmingDisconnect(false))
                  }
                >
                  {t("gateway.disconnectConfirm")}
                </Button>
                <Button variant="ghost" onClick={() => setConfirmingDisconnect(false)}>
                  {t("gateway.cancelCta")}
                </Button>
              </>
            ) : (
              <Button variant="ghost" disabled={busy} onClick={() => setConfirmingDisconnect(true)}>
                {t("gateway.disconnectCta")}
              </Button>
            )}
          </div>
        )}
        {confirmingDisconnect && (
          <p className="mt-2 text-sm text-warning-text">
            {t("gateway.disconnectConfirmTitle")} {t("gateway.disconnectConfirmBody")}
          </p>
        )}
      </Card>

      <Card>
        <SectionHeading>{t("gateway.formHeading")}</SectionHeading>
        {status.provider === TEST_PROVIDER && (
          <p role="note" className="mt-2 text-sm font-semibold text-warning-text">
            {t("gateway.testEnvNotice")}
          </p>
        )}
        <p className="mt-2 text-sm text-ink-muted">{t("gateway.writeOnlyNotice")}</p>
        <form id="gateway-credentials-form" className="mt-4 flex flex-col gap-3" onSubmit={handleSubmit}>
          {status.credential_fields.map((field) => (
            <Input
              key={field}
              label={fieldLabel(field, t)}
              type="password"
              autoComplete="off"
              value={values[field] ?? ""}
              onChange={(event) =>
                setValues((current) => ({ ...current, [field]: event.target.value }))
              }
            />
          ))}
          {formError !== null && (
            <p role="alert" className="text-sm text-danger">
              {formError}
            </p>
          )}
          <Button type="submit" disabled={busy} className="self-start">
            {t("gateway.saveCta")}
          </Button>
        </form>
      </Card>
    </div>
  );
}

// A field the platform has no Hebrew for renders its RAW name — which is an LTR
// snake_case run inside an RTL Hebrew form, so it needs BOTH the bidi isolation
// this repo already applies to non-numeric labels (VariantMatrix.tsx) and the
// WCAG 3.1.2 language mark. An axe pass cannot catch a missing one, because a
// <label> element exists either way.
//
// This case is reachable the day a real-provider adapter declares its own field
// set: the form follows with no frontend edit (that is the design working), and
// any Hebrew label keyed to a fake field name simply becomes dead.
function fieldLabel(field: string, t: (key: string) => string) {
  const key = `gateway.field.${field}`;
  const translated = t(key);
  if (translated !== key) {
    return translated;
  }
  return (
    <bdi dir="ltr" lang="en">
      {field}
    </bdi>
  );
}
