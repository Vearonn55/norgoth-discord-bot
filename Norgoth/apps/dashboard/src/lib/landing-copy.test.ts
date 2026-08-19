import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";
import {
  LANDING_FEATURE_CATALOG,
  LANDING_FEATURE_IDS,
} from "@/components/landing/landing-feature-catalog";

const LANDING_KEYS = [
  "metaTitle",
  "metaDescription",
  "skipToContent",
  "navBrand",
  "navHow",
  "navWhy",
  "navFeatures",
  "navTrust",
  "addToDiscord",
  "login",
  "openCommandCenter",
  "heroEyebrow",
  "heroLead",
  "heroTrust",
  "addNorBot",
  "valueTitle",
  "valueCommandTitle",
  "featuresTitle",
  "cardsTitle",
  "whyTitle",
  "howTitle",
  "trustTitle",
  "trustDurableTitle",
  "ctaTitle",
  "footerProduct",
  "cardsDetailClose",
] as const;

const SERVER_KEYS = [
  "notInstalled",
  "notConfigured",
  "configured",
  "continueSetup",
  "installNorBot",
  "refresh",
  "roleOwner",
  "awaitingInstall",
  "installTimedOut",
  "pageOf",
  "previousPage",
  "nextPage",
] as const;

const OVERCLAIM = /Support Teams|100%|thousands|fastest/i;
const TIKTOK = /TikTok/i;
const INFRA =
  /Redis|Postgres|Gateway|worker|queue progress|snapshot|payload|endpoint|idempotent|\bguilds?\b/i;
const ALLOWED_INFRA_PATHS = new Set([
  "oauthNotConfiguredTitle",
  "oauthNotConfiguredBody",
]);

function flattenStrings(
  value: unknown,
  prefix = "",
): Array<[string, string]> {
  if (typeof value === "string") {
    return [[prefix, value]];
  }
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) =>
      flattenStrings(nested, prefix ? `${prefix}.${key}` : key),
    );
  }
  return [];
}

describe("dictionary keys", () => {
  it("includes landing and updated servers copy in en and tr", () => {
    for (const key of LANDING_KEYS) {
      expect(en.landing[key].length).toBeGreaterThan(0);
      expect(tr.landing[key].length).toBeGreaterThan(0);
    }
    for (const key of SERVER_KEYS) {
      expect(en.servers[key].length).toBeGreaterThan(0);
      expect(tr.servers[key].length).toBeGreaterThan(0);
    }
    expect(en.servers.installNorBot).toContain("NorBot");
    expect(tr.servers.installNorBot).toContain("NorBot");
    expect(en.servers).not.toHaveProperty("addBot");
    expect(tr.servers).not.toHaveProperty("addBot");
    expect(en.dashboard.description).toContain("NorBot");
  });

  it("has complete feature copy for every catalog id in en and tr", () => {
    for (const id of LANDING_FEATURE_IDS) {
      for (const locale of [en.landing, tr.landing]) {
        const feature = locale.features[id];
        expect(feature.title.length).toBeGreaterThan(0);
        expect(feature.summary.length).toBeGreaterThan(0);
        expect(feature.body.length).toBeGreaterThan(0);
        expect(feature.cap1.length).toBeGreaterThan(0);
        expect(feature.cap2.length).toBeGreaterThan(0);
        expect(feature.cap3.length).toBeGreaterThan(0);
      }
    }
  });

  it("forbids overclaims and unfinished products in landing copy", () => {
    for (const [pathKey, text] of [
      ...flattenStrings(en.landing),
      ...flattenStrings(tr.landing),
    ]) {
      expect(text, pathKey).not.toMatch(OVERCLAIM);
      if (pathKey.includes("notifications") || pathKey === "metaDescription") {
        expect(text, pathKey).not.toMatch(TIKTOK);
      }
      if (!ALLOWED_INFRA_PATHS.has(pathKey.split(".")[0] ?? "")) {
        expect(text, pathKey).not.toMatch(INFRA);
      }
      expect(text, pathKey).not.toMatch(/\/verify/);
      expect(text, pathKey).not.toMatch(/\/community\//);
    }
  });
});

describe("visual QA tokens", () => {
  it("keeps skeleton, public scroll, landing motion, and reduced-motion gates", () => {
    const cssPath = path.join(
      path.dirname(fileURLToPath(import.meta.url)),
      "../app/globals.css",
    );
    const css = readFileSync(cssPath, "utf8");
    expect(css).toContain(".norgoth-skeleton");
    expect(css).toContain(".norgoth-public");
    expect(css).toContain("overflow-y: auto");
    expect(css).toContain(".norgoth-landing-reveal");
    expect(css).toContain(".norgoth-skip-link");
    expect(css).toContain("scroll-padding-top");
    expect(css).toContain(".norgoth-landing-feature-row");
    expect(css).toContain(".norgoth-landing-cards");
    expect(css).toContain("repeat(auto-fill, minmax(220px, 1fr))");
    expect(css).toContain(".norgoth-landing-mock-badge");
    expect(css).toContain(".norgoth-landing-mock-feature");
    expect(css).toContain(".norgoth-landing-card-title");
    expect(css).toContain(".norgoth-landing-card-summary");
    expect(css).toContain("overflow: hidden");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(css).toContain(".norgoth-server-guild-action");
    expect(css).toContain("min-height: 40px");
  });

  it("covers the 375 / 768 / 1280 and keyboard checklist in CSS primitives", () => {
    const cssPath = path.join(
      path.dirname(fileURLToPath(import.meta.url)),
      "../app/globals.css",
    );
    const css = readFileSync(cssPath, "utf8");
    expect(css).toContain(".norgoth-mini-card:focus-visible");
    expect(css).toContain("transform: none");
    expect(css).toContain(".norgoth-landing-hero");
    expect(css).toContain("min-height: 28rem");
  });
});

describe("landing source contracts", () => {
  const srcRoot = path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
  );

  it("keeps card a11y attributes and reduced-motion helper", () => {
    const card = readFileSync(
      path.join(srcRoot, "components/landing/landing-feature-card.tsx"),
      "utf8",
    );
    const grid = readFileSync(
      path.join(srcRoot, "components/landing/landing-feature-card-grid.tsx"),
      "utf8",
    );
    const motion = readFileSync(
      path.join(srcRoot, "components/landing/landing-motion.tsx"),
      "utf8",
    );
    const row = readFileSync(
      path.join(srcRoot, "components/landing/landing-feature-row.tsx"),
      "utf8",
    );
    const visual = readFileSync(
      path.join(srcRoot, "components/landing/landing-feature-visual.tsx"),
      "utf8",
    );
    expect(card).toContain("aria-expanded");
    expect(card).toContain('aria-controls={LANDING_FEATURE_DETAIL_ID}');
    expect(grid).toContain("norgoth-landing-cards");
    expect(grid).toContain("norgoth-landing-card-detail");
    expect(grid).toContain("useReducedMotion");
    expect(grid).toContain("LANDING_FEATURE_DETAIL_ID");
    expect(row).not.toContain("demoSidebar");
    expect(visual).toContain("groupLabel");
    expect(motion).toContain("useReducedMotion");
    expect(motion).toContain("LazyMotion");
    expect(motion).toContain("domAnimation");
  });

  it("isolates motion to landing and keeps login redirect unchanged", () => {
    const landingDir = path.join(srcRoot, "components/landing");
    const files = [
      "landing-motion.tsx",
      "landing-hero.tsx",
      "landing-section.tsx",
      "landing-feature-row.tsx",
      "landing-feature-card.tsx",
      "landing-feature-card-grid.tsx",
    ];
    for (const file of files) {
      const source = readFileSync(path.join(landingDir, file), "utf8");
      expect(source).not.toContain("recharts");
      expect(source).not.toContain("tinymce");
    }
    const shell = readFileSync(
      path.join(srcRoot, "components/layout/app-shell.tsx"),
      "utf8",
    );
    expect(shell).not.toContain("motion/react");
    expect(shell).not.toContain('from "motion"');
    const login = readFileSync(
      path.join(srcRoot, "app/[lang]/(public)/login/page.tsx"),
      "utf8",
    );
    expect(login).toContain(
      "`/norgoth-api/api/v1/oauth/discord/dashboard/authorize?lang=${encodeURIComponent(lang)}`",
    );
    const page = readFileSync(
      path.join(srcRoot, "app/[lang]/(public)/page.tsx"),
      "utf8",
    );
    expect(page).toContain("alternates");
    expect(page).toContain("languages");
  });

  it("does not use unsafe HTML in the landing directory", () => {
    const landingDir = path.join(srcRoot, "components/landing");
    const names = [
      "landing-page.tsx",
      "landing-nav.tsx",
      "landing-hero.tsx",
      "landing-value.tsx",
      "landing-features.tsx",
      "landing-why.tsx",
      "landing-how-it-works.tsx",
      "landing-trust.tsx",
      "landing-cta.tsx",
      "landing-footer.tsx",
      "landing-feature-card.tsx",
      "landing-feature-card-grid.tsx",
      "landing-feature-visual.tsx",
      "landing-oauth-alerts.tsx",
    ];
    for (const name of names) {
      const source = readFileSync(path.join(landingDir, name), "utf8");
      expect(source).not.toContain("dangerouslySetInnerHTML");
    }
  });

  it("catalog ids match the production landing inventory", () => {
    expect(LANDING_FEATURE_CATALOG.map((item) => item.id)).toEqual([
      ...LANDING_FEATURE_IDS,
    ]);
    expect(LANDING_FEATURE_IDS).not.toContain("supportTeams");
  });
});
