import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import {
  formatVerificationValidationIssues,
  resolveVerificationValidationError,
} from "@/lib/verification/validation-errors";

describe("resolveVerificationValidationError", () => {
  const errors = en.verificationPage.validationErrors;
  const fields = {
    verificationChannel: en.verificationPage.verificationChannel,
    logChannel: en.verificationPage.logChannel,
    unverifiedRole: en.verificationPage.unverifiedRole,
    memberRole: en.verificationPage.memberRole,
    manualReviewRole: en.verificationPage.manualReviewRole,
  };

  it("maps known codes to localized dashboard copy", () => {
    expect(
      resolveVerificationValidationError(
        "role_hierarchy_invalid",
        null,
        errors,
        fields,
      ),
    ).toBe(errors.role_hierarchy_invalid);
  });

  it("formats field-specific channel permission errors", () => {
    const message = resolveVerificationValidationError(
      "missing_bot_permissions",
      "verification_channel_id",
      errors,
      fields,
    );
    expect(message).toContain(fields.verificationChannel);
  });

  it("joins multiple validation issues without duplicates", () => {
    const message = formatVerificationValidationIssues(
      [
        { code: "role_managed", field: "unverified_role_id" },
        { code: "role_hierarchy_invalid", field: "member_role_id" },
      ],
      errors,
      fields,
    );
    expect(message).toContain(errors.role_managed);
    expect(message).toContain(errors.role_hierarchy_invalid);
  });
});
