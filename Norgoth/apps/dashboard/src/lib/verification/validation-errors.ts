export type VerificationValidationIssue = {
  code: string;
  field?: string | null;
  message?: string | null;
  channel_id?: string | null;
  channel_name?: string | null;
  missing_permissions?: string[] | null;
  overwrite_scope?: string | null;
};

type ValidationErrorDict = {
  verification_setup_incomplete?: string;
  verification_not_configured?: string;
  bot_not_installed?: string;
  missing_bot_permissions?: string;
  missingGuildRolePermissions?: string;
  missingChannelPermissions?: string;
  missingChannelPermissionsCategory?: string;
  unsupportedChannelType?: string;
  channelNotFound?: string;
  discord_resource_not_in_guild?: string;
  role_managed?: string;
  role_hierarchy_invalid?: string;
  guild_metadata_unavailable?: string;
  discord_rate_limited?: string;
  discord_unavailable?: string;
  validationUnexpected?: string;
  roleMissing?: string;
  permissionLabelViewChannel?: string;
  permissionLabelSendMessages?: string;
  permissionLabelEmbedLinks?: string;
};

type FieldLabelDict = {
  verificationChannel?: string;
  logChannel?: string;
  unverifiedRole?: string;
  memberRole?: string;
  manualReviewRole?: string;
};

function formatPermissionList(
  permissions: string[],
  errors: ValidationErrorDict,
): string {
  const localized = permissions.map((permission) =>
    localizePermissionLabel(permission, errors),
  );
  if (localized.length <= 1) {
    return localized[0] ?? "";
  }
  if (localized.length === 2) {
    return `${localized[0]} and ${localized[1]}`;
  }
  return `${localized.slice(0, -1).join(", ")}, and ${localized.at(-1)}`;
}

function localizePermissionLabel(
  permission: string,
  errors: ValidationErrorDict,
): string {
  switch (permission) {
    case "View Channel":
      return errors.permissionLabelViewChannel ?? permission;
    case "Send Messages":
      return errors.permissionLabelSendMessages ?? permission;
    case "Embed Links":
      return errors.permissionLabelEmbedLinks ?? permission;
    default:
      return permission;
  }
}

export function verificationIssuesNeedPermissionUpdate(
  issues: VerificationValidationIssue[],
): boolean {
  return issues.some(
    (issue) =>
      issue.code === "missing_channel_permissions" ||
      issue.code === "missing_bot_permissions",
  );
}

export function resolveVerificationValidationError(
  issue: VerificationValidationIssue,
  errors: ValidationErrorDict,
  fieldLabels: FieldLabelDict,
): string {
  const { code, field, channel_name: channelName, missing_permissions: missingPermissions, overwrite_scope: overwriteScope } =
    issue;
  const fieldLabel = field ? fieldLabelsFor(field, fieldLabels) : null;

  if (code === "missing_channel_permissions") {
    const channel = channelName ? `#${channelName}` : fieldLabel ?? "channel";
    const permissions = missingPermissions?.length
      ? formatPermissionList(missingPermissions, errors)
      : "";
    const template =
      overwriteScope === "category"
        ? errors.missingChannelPermissionsCategory
        : errors.missingChannelPermissions;
    if (template) {
      return template
        .replace("{channel}", channel)
        .replace("{permissions}", permissions);
    }
    return issue.message ?? code;
  }

  if (code === "missing_bot_permissions" && !field) {
    return errors.missingGuildRolePermissions ?? errors.missing_bot_permissions ?? code;
  }

  if (code === "discord_resource_not_in_guild" && fieldLabel) {
    return (
      errors.roleMissing?.replace("{field}", fieldLabel) ??
      errors.discord_resource_not_in_guild ??
      code
    );
  }

  if (code === "unsupported_verification_channel_type") {
    return errors.unsupportedChannelType ?? issue.message ?? code;
  }

  const mapped = errors[code as keyof ValidationErrorDict];
  if (typeof mapped === "string" && mapped.length > 0) {
    return mapped;
  }

  if (issue.message) {
    return issue.message;
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
    resolveVerificationValidationError(issue, errors, fieldLabels),
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
