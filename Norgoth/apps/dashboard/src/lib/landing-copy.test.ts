import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";
import { splitItems } from "@/components/landing/landing-copy";

const LANDING_KEYS = [
  "metaTitle",
  "metaDescription",
  "navBrand",
  "navHow",
  "navFeatures",
  "addToDiscord",
  "login",
  "heroEyebrow",
  "heroLead",
  "addNorBot",
  "valueTitle",
  "featuresTitle",
  "howTitle",
  "trustTitle",
  "ctaTitle",
  "footerProduct",
] as const;

const SERVER_KEYS = [
  "addBot",
  "notInstalled",
  "notConfigured",
  "configured",
  "continueSetup",
  "installNorBot",
  "refresh",
  "roleOwner",
] as const;

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
    expect(en.servers.addBot).toContain("NorBot");
    expect(tr.servers.addBot).toContain("NorBot");
    expect(en.dashboard.description).toContain("NorBot");
  });

  it("keeps six shipped feature categories", () => {
    expect(splitItems(en.landing.featureCommunityItems)).toHaveLength(5);
    expect(splitItems(en.landing.featureModerationItems)).toHaveLength(5);
    expect(splitItems(en.landing.featureCommunicationItems)).toHaveLength(4);
    expect(splitItems(en.landing.featureSupportItems)).toHaveLength(3);
    expect(splitItems(en.landing.featureAutomationItems)).toHaveLength(3);
    expect(splitItems(en.landing.featureOperationsItems)).toHaveLength(3);
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
