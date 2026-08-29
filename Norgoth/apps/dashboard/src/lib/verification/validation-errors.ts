export type VerificationValidationIssue = {
  code: string;
  field?: string | null;
  message?: string | null;
};

type ValidationErrorDict = {
  verification_setup_incomplete?: string;
  verification_not_configured?: string;
  bot_not_installed?: string;
  missing_bot_permissions?: string;
  discord_resource_not_in_guild?: string;
  role_managed?: string;
  role_hierarchy_invalid?: string;
  guild_metadata_unavailable?: string;
  discord_rate_limited?: string;
  discord_unavailable?: string;
  validationUnexpected?: string;
  channelPermissions?: string;
  roleMissing?: string;
};

type FieldLabelDict = {
  verificationChannel?: string;
  logChannel?: string;
  unverifiedRole?: string;
  memberRole?: string;
  manualReviewRole?: string;
};

export function resolveVerificationValidationError(
  code: string,
  field: string | null | undefined,
  errors: ValidationErrorDict,
  fieldLabels: FieldLabelDict,
): string {
  const fieldLabel = field ? fieldLabelsFor(field, fieldLabels) : null;

  if (code === "missing_bot_permissions" && fieldLabel) {
    return (
      errors.channelPermissions?.replace("{field}", fieldLabel) ??
      errors.missing_bot_permissions ??
      code
    );
  }

  if (code === "discord_resource_not_in_guild" && fieldLabel) {
    return (
      errors.roleMissing?.replace("{field}", fieldLabel) ??
      errors.discord_resource_not_in_guild ??
      code
    );
  }

  const mapped = errors[code as keyof ValidationErrorDict];
  if (typeof mapped === "string" && mapped.length > 0) {
    return mapped;
  }

  return errors.validationUnexpected ?? "Validation failed.";
}

export function formatVerificationValidationIssues(
  issues: VerificationValidationIssue[],
  errors: ValidationErrorDict,
  fieldLabels: FieldLabelDict,
): string {
  if (!issues.length) {
    return errors.validationUnexpected ?? "Validation failed.";
  }

  const messages = issues.map((issue) =>
    resolveVerificationValidationError(
      issue.code,
      issue.field,
      errors,
      fieldLabels,
    ),
  );

  const unique = [...new Set(messages)];
  return unique.join(" ");
}

function fieldLabelsFor(field: string, labels: FieldLabelDict): string | null {
  switch (field) {
    case "verification_channel_id":
      return labels.verificationChannel ?? field;
    case "log_channel_id":
      return labels.logChannel ?? field;
    case "unverified_role_id":
      return labels.unverifiedRole ?? field;
    case "member_role_id":
      return labels.memberRole ?? field;
    case "manual_review_role_id":
      return labels.manualReviewRole ?? field;
    default:
      return field;
  }
}
