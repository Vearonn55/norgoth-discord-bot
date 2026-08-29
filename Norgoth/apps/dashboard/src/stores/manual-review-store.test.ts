import { describe, expect, it } from "vitest";

import {
  manualReviewDetailErrorKey,
  manualReviewListErrorKey,
} from "@/stores/manual-review-store";

describe("manualReviewListErrorKey", () => {
  it("maps HTTP statuses to queue error keys", () => {
    expect(manualReviewListErrorKey(404)).toBe("queueNotFound");
    expect(manualReviewListErrorKey(403)).toBe("queueForbidden");
    expect(manualReviewListErrorKey(500)).toBe("queueLoadError");
  });
});

describe("manualReviewDetailErrorKey", () => {
  it("maps HTTP statuses to detail error keys", () => {
    expect(manualReviewDetailErrorKey(404)).toBe("detailNotFound");
    expect(manualReviewDetailErrorKey(403)).toBe("detailForbidden");
    expect(manualReviewDetailErrorKey(502)).toBe("detailLoadError");
  });
});
