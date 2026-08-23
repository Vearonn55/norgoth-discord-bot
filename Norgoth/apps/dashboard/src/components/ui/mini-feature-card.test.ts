import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MiniFeatureCard } from "@/components/ui/mini-feature-card";
import { cilSettings } from "@coreui/icons";

const miniCardPath = resolve(
  import.meta.dirname,
  "mini-feature-card.tsx"
);

describe("MiniFeatureCard equalizeFooter", () => {
  it("renders footer spacer class when equalizeFooter is set without toggle", () => {
    const html = renderToStaticMarkup(
      <MiniFeatureCard
        icon={cilSettings}
        name="Configuration"
        description="Trap channels"
        onClick={() => undefined}
        equalizeFooter
      />
    );
    expect(html).toContain("norgoth-mini-card-footer-spacer");
    expect(html).toContain("flex-column");
  });

  it("exports equalizeFooter prop in component source", () => {
    const src = readFileSync(miniCardPath, "utf8");
    expect(src).toContain("equalizeFooter");
    expect(src).toContain("norgoth-mini-card-footer-spacer");
  });
});
