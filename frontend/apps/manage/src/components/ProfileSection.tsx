import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { Settings } from "../api";
import {
  cardClass,
  ErrorNotice,
  inputClass,
  labelClass,
  Loading,
  primaryButtonClass,
  SavedNotice,
} from "./shared";

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
  const [profile, setProfile] = useState<ProfileForm | null>(null);
  const [toggles, setToggles] = useState<TogglesForm>({
    deposits_enabled: false,
    brides_only: false,
  });
  const [error, setError] = useState<string | null>(null);
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
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setError(errorMessage(loadError));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (profile === null) {
    return error !== null ? <ErrorNotice message={error} /> : <Loading />;
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
      setError(null);
      setSaved(true);
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className={`${cardClass} space-y-4`}>
      <h3 className="text-sm font-semibold">פרופיל הבוטיק</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="profile-phone">
            טלפון
          </label>
          <input
            id="profile-phone"
            type="tel"
            dir="ltr"
            className={inputClass}
            value={profile.phone}
            onChange={(event) => setField("phone", event.target.value)}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="profile-address">
            כתובת
          </label>
          <input
            id="profile-address"
            className={inputClass}
            value={profile.address}
            onChange={(event) => setField("address", event.target.value)}
          />
        </div>
      </div>
      <div>
        <label className={labelClass} htmlFor="profile-maps-url">
          קישור למפות (http/https)
        </label>
        <input
          id="profile-maps-url"
          type="url"
          dir="ltr"
          className={inputClass}
          value={profile.maps_url}
          onChange={(event) => setField("maps_url", event.target.value)}
        />
      </div>
      <div>
        <label className={labelClass} htmlFor="profile-description">
          תיאור
        </label>
        <textarea
          id="profile-description"
          rows={4}
          className={inputClass}
          value={profile.description}
          onChange={(event) => setField("description", event.target.value)}
        />
      </div>

      <h3 className="pt-2 text-sm font-semibold">הגדרות</h3>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={toggles.deposits_enabled}
          onChange={(event) => {
            setToggles({ ...toggles, deposits_enabled: event.target.checked });
            setSaved(false);
          }}
        />
        גביית מקדמות מופעלת
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={toggles.brides_only}
          onChange={(event) => {
            setToggles({ ...toggles, brides_only: event.target.checked });
            setSaved(false);
          }}
        />
        בוטיק לכלות בלבד (כל סוגי התורים יוצגו לכלות בלבד)
      </label>

      {error !== null && <ErrorNotice message={error} />}
      {saved && <SavedNotice />}
      <button type="submit" className={primaryButtonClass} disabled={saving}>
        שמירת פרופיל והגדרות
      </button>
    </form>
  );
}
