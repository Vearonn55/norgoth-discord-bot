import { describe, expect, it } from "vitest";
import { useFeatureMuting } from "@/components/ui/feature-muting";

// `useFeatureMuting` is a pure function of its `enabled` argument (it calls no
// React hooks internally), so it can be exercised directly.
describe("useFeatureMuting", () => {
  it("returns non-muting props when enabled", () => {
    const props = useFeatureMuting(true);
    expect(props["data-muted"]).toBe(false);
    expect(props["aria-disabled"]).toBeUndefined();
    expect(props.inert).toBeUndefined();
    expect(props.style?.pointerEvents).toBeUndefined();
  });

  it("mutes and disables interaction when disabled", () => {
    const props = useFeatureMuting(false);
    expect(props["data-muted"]).toBe(true);
    expect(props["aria-disabled"]).toBe(true);
    expect(props.inert).toBe(true);
    expect(props.style?.pointerEvents).toBe("none");
    expect(props.style?.opacity).toBeLessThan(1);
  });
});
