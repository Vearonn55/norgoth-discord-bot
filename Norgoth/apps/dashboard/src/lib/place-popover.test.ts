import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { placePopover } from "@/lib/place-popover";

describe("placePopover", () => {
  const popover = { width: 220, height: 180 };
  const viewport = { width: 1280, height: 720 };

  it("places below the trigger when there is room", () => {
    const placed = placePopover(
      { top: 40, left: 80, width: 120, height: 32, bottom: 72, right: 200 },
      popover,
      viewport,
    );
    expect(placed.placement).toBe("bottom-start");
    expect(placed.top).toBe(76);
    expect(placed.left).toBe(80);
  });

  it("flips above the trigger near the bottom of the viewport", () => {
    const placed = placePopover(
      { top: 640, left: 40, width: 100, height: 32, bottom: 672, right: 140 },
      popover,
      viewport,
    );
    expect(placed.placement).toBe("top-start");
    expect(placed.top).toBe(640 - 180 - 4);
    expect(placed.left).toBe(40);
  });

  it("shifts left so the panel stays inside a narrow viewport", () => {
    const placed = placePopover(
      { top: 20, left: 300, width: 80, height: 28, bottom: 48, right: 380 },
      popover,
      { width: 375, height: 800 },
    );
    expect(placed.left + popover.width).toBeLessThanOrEqual(375 - 8);
    expect(placed.left).toBeGreaterThanOrEqual(8);
    expect(popover.width).toBeLessThanOrEqual(375);
  });
});

describe("EmbedColorPicker portal", () => {
  it("portals the panel to document.body", () => {
    const src = readFileSync(
      resolve(__dirname, "../components/discord/embed-color-picker.tsx"),
      "utf8",
    );
    expect(src).toContain("createPortal");
    expect(src).toContain("placePopover");
    expect(src).toContain("1080");
    expect(src).toContain('visibility: placed ? "visible" : "hidden"');
  });
});
