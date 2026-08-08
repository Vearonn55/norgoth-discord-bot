export type UserPreferences = {
  locale: "en" | "tr";
  compactSidebar: boolean;
  denseTables: boolean;
  reducedMotion: boolean;
  stickyTopbar: boolean;
};

const STORAGE_KEY = "norgoth:user-preferences";

export const DEFAULT_PREFERENCES: UserPreferences = {
  locale: "en",
  compactSidebar: false,
  denseTables: false,
  reducedMotion: false,
  stickyTopbar: true,
};

function isBrowser() {
  return typeof window !== "undefined";
}

export function getUserPreferences(): UserPreferences {
  if (!isBrowser()) return DEFAULT_PREFERENCES;

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;

    const parsed = JSON.parse(raw) as Partial<UserPreferences>;

    return {
      locale:
        parsed.locale === "tr" || parsed.locale === "en"
          ? parsed.locale
          : DEFAULT_PREFERENCES.locale,
      compactSidebar:
        typeof parsed.compactSidebar === "boolean"
          ? parsed.compactSidebar
          : DEFAULT_PREFERENCES.compactSidebar,
      denseTables:
        typeof parsed.denseTables === "boolean"
          ? parsed.denseTables
          : DEFAULT_PREFERENCES.denseTables,
      reducedMotion:
        typeof parsed.reducedMotion === "boolean"
          ? parsed.reducedMotion
          : DEFAULT_PREFERENCES.reducedMotion,
      stickyTopbar:
        typeof parsed.stickyTopbar === "boolean"
          ? parsed.stickyTopbar
          : DEFAULT_PREFERENCES.stickyTopbar,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function saveUserPreferences(preferences: UserPreferences) {
  if (!isBrowser()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
}

export function resetUserPreferences() {
  if (!isBrowser()) return;
  window.localStorage.removeItem(STORAGE_KEY);
}
