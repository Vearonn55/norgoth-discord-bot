export type StoredActivityItem = {
  id: string;
  title: string;
  meta: string;
  type: "neutral" | "success" | "warning" | "danger" | "info";
  created_at: string;
};

const STORAGE_KEY = "norgoth_activity_feed";

export function getStoredActivities(): StoredActivityItem[] {
  if (typeof window === "undefined") return [];

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];

  try {
    return JSON.parse(raw) as StoredActivityItem[];
  } catch {
    return [];
  }
}

export function addStoredActivity(item: StoredActivityItem) {
  if (typeof window === "undefined") return;

  const current = getStoredActivities();
  const next = [item, ...current].slice(0, 20);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}
