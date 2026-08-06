import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input, SectionHeading, Skeleton, TextArea, useToast } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { Settings } from "../api";
import { TogglesMatrix } from "./TogglesMatrix";

interface ProfileForm {
  phone: string;
  address: string;
  description: string;
  maps_url: string;
  essence: string;
  instagram: string;
}

// F27 D7: the toggles half is gone. `TogglesMatrix` owns every switch, renders
// them from the registry and saves each one on flip — so this function is back
// to what its name says.
function fromSettings(settings: Settings): ProfileForm {
  return {
    phone: settings.profile.phone ?? "",
    address: settings.profile.address ?? "",
    description: settings.profile.description ?? "",
    maps_url: settings.profile.maps_url ?? "",
    essence: settings.profile.essence ?? "",
    instagram: settings.profile.instagram ?? "",
  };
}

export function ProfileSection() {
  const { t } = useTranslation();
  const toast = useToast();
  const [profile, setProfile] = useState<ProfileForm | null>(null);
  // The matrix's initial rows, straight off this section's ONE fetch — no second
  // GET (design §2). Held rather than passed through, because the section
  // renders a Skeleton until the fetch lands.
  const [toggles, setToggles] = useState<Record<string, boolean> | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getSettings()
      .then((settings) => {
        if (!cancelled) {
          setProfile(fromSettings(settings));
          setToggles(settings.toggles);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(errorMessage(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (profile === null || toggles === null) {
    if (loadError !== null) {
      return (
        <p role="alert" className="text-base text-ink-muted">
          {loadError}
        </p>
      );
    }
    return <Skeleton variant="text" lines={4} />;
  }

  const setField = (field: keyof ProfileForm, value: string) => {
    setProfile({ ...profile, [field]: value });
    setSaved(false);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      // ⚠ PROFILE ONLY. The toggles used to ride this payload, and the whole
      // point of D7 is that they no longer do: each switch saves itself, and a
      // profile save that also sent the toggles would race the matrix's own
      // writes with a stale copy of them.
      const updated = await api.updateSettings({ profile });
      setProfile(fromSettings(updated));
      setSaved(true);
    } catch (saveError) {
      toast({ message: errorMessage(saveError), variant: "error" });
    } finally {
      setSaving(false);
    }
  };

  const form = (
    <Card>
      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
        <SectionHeading as="h2">{t("profile.heading")}</SectionHeading>
        {/* Feature 10 turns these fields world-readable. The disclosure belongs
            under THIS heading, which covers them — not under the toggles
            heading, whose settings are never published. */}
        <p className="text-xs text-ink-muted">{t("profile.publicNotice")}</p>
        <Input
          label={t("profile.essence")}
          value={profile.essence}
          onChange={(event) => setField("essence", event.target.value)}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label={t("profile.phone")}
            type="tel"
            dir="ltr"
            value={profile.phone}
            onChange={(event) => setField("phone", event.target.value)}
          />
          <Input
            label={t("profile.address")}
            value={profile.address}
            onChange={(event) => setField("address", event.target.value)}
          />
        </div>
        <Input
          label={t("profile.mapsUrl")}
          type="url"
          dir="ltr"
          value={profile.maps_url}
          onChange={(event) => setField("maps_url", event.target.value)}
        />
        <Input
          label={t("profile.instagram")}
          help={t("profile.instagramHint")}
          dir="ltr"
          value={profile.instagram}
          onChange={(event) => setField("instagram", event.target.value)}
        />
        <TextArea
          label={t("profile.description")}
          rows={4}
          value={profile.description}
          onChange={(event) => setField("description", event.target.value)}
        />

        <div className="flex items-center gap-3">
          <Button type="submit" loading={saving}>
            {t("profile.save")}
          </Button>
          {saved && <span className="text-xs text-ink-muted">{t("common.saved")}</span>}
        </div>
      </form>
    </Card>
  );

  // The matrix is a sibling CARD under the form, not a section of its own — no
  // sixteenth `SectionKey`, no nav row, no guide-steps entry (D7). Its saved cue
  // is its own state, so a row flip never lights the profile form's (F-T1).
  return (
    <div className="flex flex-col gap-6">
      {form}
      <TogglesMatrix toggles={toggles} />
    </div>
  );
}
