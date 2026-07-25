import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input, SectionHeading, Skeleton, TextArea, Toggle, useToast } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { Settings } from "../api";

interface ProfileForm {
  phone: string;
  address: string;
  description: string;
  maps_url: string;
}

interface TogglesForm {
  deposits_enabled: boolean;
  brides_only: boolean;
}

function fromSettings(settings: Settings): { profile: ProfileForm; toggles: TogglesForm } {
  return {
    profile: {
      phone: settings.profile.phone ?? "",
      address: settings.profile.address ?? "",
      description: settings.profile.description ?? "",
      maps_url: settings.profile.maps_url ?? "",
    },
    toggles: {
      deposits_enabled: settings.toggles.deposits_enabled ?? false,
      brides_only: settings.toggles.brides_only ?? false,
    },
  };
}

export function ProfileSection() {
  const { t } = useTranslation();
  const toast = useToast();
  const [profile, setProfile] = useState<ProfileForm | null>(null);
  const [toggles, setToggles] = useState<TogglesForm>({ deposits_enabled: false, brides_only: false });
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getSettings()
      .then((settings) => {
        if (!cancelled) {
          const loaded = fromSettings(settings);
          setProfile(loaded.profile);
          setToggles(loaded.toggles);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(errorMessage(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (profile === null) {
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
      const updated = await api.updateSettings({ profile, toggles });
      const synced = fromSettings(updated);
      setProfile(synced.profile);
      setToggles(synced.toggles);
      setSaved(true);
    } catch (saveError) {
      toast({ message: errorMessage(saveError), variant: "error" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
        <SectionHeading as="h2">{t("profile.heading")}</SectionHeading>
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
        <TextArea
          label={t("profile.description")}
          rows={4}
          value={profile.description}
          onChange={(event) => setField("description", event.target.value)}
        />

        <SectionHeading as="h2">{t("profile.settingsHeading")}</SectionHeading>
        <Toggle
          label={t("profile.depositsEnabled")}
          checked={toggles.deposits_enabled}
          onCheckedChange={(value) => {
            setToggles({ ...toggles, deposits_enabled: value });
            setSaved(false);
          }}
        />
        <Toggle
          label={t("profile.bridesOnly")}
          description={t("profile.bridesOnlyHint")}
          checked={toggles.brides_only}
          onCheckedChange={(value) => {
            setToggles({ ...toggles, brides_only: value });
            setSaved(false);
          }}
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
}
