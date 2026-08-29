import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import {
  formatVerificationValidationIssues,
  resolveVerificationValidationError,
  verificationIssuesNeedPermissionUpdate,
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
        { code: "role_hierarchy_invalid" },
        errors,
        fields,
      ),
    ).toBe(errors.role_hierarchy_invalid);
  });

  it("formats structured channel permission errors with channel name and subset", () => {
    const message = resolveVerificationValidationError(
      {
        code: "missing_channel_permissions",
        field: "verification_channel_id",
        channel_name: "verification",
        missing_permissions: ["Embed Links", "Send Messages"],
      },
      errors,
      fields,
    );
    expect(message).toContain("#verification");
    expect(message).toContain("Embed Links");
    expect(message).toContain("Send Messages");
    expect(message).not.toContain("Read Message History");
  });

  it("uses category overwrite copy when scope is category", () => {
    const message = resolveVerificationValidationError(
      {
        code: "missing_channel_permissions",
        channel_name: "verification",
        missing_permissions: ["Send Messages"],
        overwrite_scope: "category",
      },
      errors,
      fields,
    );
    expect(message).toBe(errors.missingChannelPermissionsCategory
      .replace("{channel}", "#verification")
      .replace("{permissions}", "Send Messages"));
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

  it("detects permission recovery issues", () => {
    expect(
      verificationIssuesNeedPermissionUpdate([
        { code: "missing_channel_permissions" },
      ]),
    ).toBe(true);
    expect(
      verificationIssuesNeedPermissionUpdate([{ code: "role_managed" }]),
    ).toBe(false);
  });
});
