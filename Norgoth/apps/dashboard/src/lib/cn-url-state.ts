export const CN_PAGE_SIZE = 10;

export const CN_FUNCTIONAL_PLATFORMS = ["youtube", "twitch", "kick", "x"] as const;

export const CN_PANELS = [
  "templates",
  "sender-styles",
  "history",
  "analytics",
  "add",
  "edit",
] as const;

export type CnFunctionalPlatform = (typeof CN_FUNCTIONAL_PLATFORMS)[number];
export type CnPlatformFilter = "all" | CnFunctionalPlatform;
export type CnPanel = (typeof CN_PANELS)[number];

export type CnUrlState = {
  platform: CnPlatformFilter;
  page: number;
  panel: CnPanel | null;
  account: string | null;
};

export const EVENT_TYPES_BY_PLATFORM: Record<string, string[]> = {
  youtube: ["VIDEO_PUBLISHED"],
  twitch: ["STREAM_STARTED", "STREAM_ENDED"],
  kick: ["STREAM_STARTED", "STREAM_ENDED"],
  x: ["POST_PUBLISHED"],
  tiktok: ["VIDEO_PUBLISHED"],
};

export const PLATFORM_CHART_COLORS: Record<string, string> = {
  youtube: "#FF6B6B",
  twitch: "#A78BFA",
  kick: "#34D399",
  x: "#E5E7EB",
};

function isFunctionalPlatform(value: string): value is CnFunctionalPlatform {
  return (CN_FUNCTIONAL_PLATFORMS as readonly string[]).includes(value);
}

function isPanel(value: string): value is CnPanel {
  return (CN_PANELS as readonly string[]).includes(value);
}

export function parseCnUrlState(
  params: URLSearchParams | { get: (key: string) => string | null },
): CnUrlState {
  const platformRaw = (params.get("platform") ?? "all").trim().toLowerCase();
  const platform: CnPlatformFilter = isFunctionalPlatform(platformRaw)
    ? platformRaw
    : "all";
  const pageRaw = Number.parseInt(params.get("page") ?? "1", 10);
  const page = Number.isFinite(pageRaw) && pageRaw > 0 ? pageRaw : 1;
  const panelRaw = (params.get("panel") ?? "").trim();
  const panel = isPanel(panelRaw) ? panelRaw : null;
  const account = (params.get("account") ?? "").trim() || null;
  return {
    platform,
    page,
    panel: panel === "edit" && !account ? null : panel,
    account: panel === "edit" ? account : null,
  };
}

export function serializeCnUrlState(state: CnUrlState): string {
  const params = new URLSearchParams();
  if (state.platform !== "all") params.set("platform", state.platform);
  if (state.page > 1) params.set("page", String(state.page));
  if (state.panel) params.set("panel", state.panel);
  if (state.panel === "edit" && state.account) {
    params.set("account", state.account);
  }
  return params.toString();
}

export function withCnPlatform(
  state: CnUrlState,
  platform: CnPlatformFilter,
): CnUrlState {
  return { ...state, platform, page: 1 };
}

export function clampPage(
  page: number,
  total: number,
  pageSize: number = CN_PAGE_SIZE,
): number {
  const totalPages = Math.max(1, Math.ceil(Math.max(0, total) / pageSize));
  return Math.min(Math.max(1, page), totalPages);
}

export function accountsListQuery(opts: {
  platform?: string | null;
  limit?: number;
  offset?: number;
}): string {
  const params = new URLSearchParams();
  const platform = opts.platform?.trim();
  if (platform && platform !== "all") params.set("platform", platform);
  params.set("limit", String(opts.limit ?? CN_PAGE_SIZE));
  params.set("offset", String(opts.offset ?? 0));
  return params.toString();
}

export function shouldCloseDirtyModal(
  dirty: boolean,
  confirmed: boolean,
): boolean {
  return !dirty || confirmed;
}

export function confirmDirtyClose(dirty: boolean, message: string): boolean {
  if (!dirty) return true;
  if (typeof window === "undefined") return false;
  return window.confirm(message);
}

export function prefersReducedMotion(): boolean {
  if (typeof document !== "undefined") {
    if (document.documentElement.dataset.reducedMotion === "true") return true;
  }
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  return false;
}
