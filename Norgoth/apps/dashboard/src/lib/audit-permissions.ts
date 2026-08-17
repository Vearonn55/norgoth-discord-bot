import { formatDict, type LocaleDict } from "@/lib/locale-format";

export const AUDIT_FIELD_KEYS = [
  "name",
  "topic",
  "nsfw",
  "slowmode_delay",
  "parent",
  "position",
  "type",
  "bitrate",
  "user_limit",
  "archived",
  "locked",
  "auto_archive_duration",
  "color",
  "hoist",
  "mentionable",
  "icon",
  "unicode_emoji",
] as const;

export type AuditFieldKey = (typeof AUDIT_FIELD_KEYS)[number];

const FIELD_DICT_KEY: Record<AuditFieldKey, keyof LocaleDict["auditLogsPage"]> = {
  name: "fieldName",
  topic: "fieldTopic",
  nsfw: "fieldNsfw",
  slowmode_delay: "fieldSlowmode",
  parent: "fieldParent",
  position: "fieldPosition",
  type: "fieldType",
  bitrate: "fieldBitrate",
  user_limit: "fieldUserLimit",
  archived: "fieldArchived",
  locked: "fieldLocked",
  auto_archive_duration: "fieldAutoArchive",
  color: "fieldColor",
  hoist: "fieldHoist",
  mentionable: "fieldMentionable",
  icon: "fieldIcon",
  unicode_emoji: "fieldEmoji",
};

export function auditFieldLabel(dict: LocaleDict, field: string): string {
  if (field in FIELD_DICT_KEY) {
    const key = FIELD_DICT_KEY[field as AuditFieldKey];
    return dict.auditLogsPage[key];
  }
  return field;
}

export function auditPermissionLabel(
  dict: LocaleDict,
  permission: string,
  unknownMask?: string | null,
): string {
  if (permission === "unknown") {
    return formatDict(dict.auditLogsPage.unknownPermission, {
      mask: unknownMask || "0x0",
    });
  }
  const mapped = (dict.auditPermissions as Record<string, string | undefined>)[permission];
  if (typeof mapped === "string" && mapped) {
    return mapped;
  }
  if (unknownMask) {
    return formatDict(dict.auditLogsPage.unknownPermission, { mask: unknownMask });
  }
  return permission.replaceAll("_", " ");
}

export function formatAuditValue(value: unknown): string {
  if (value == null || value === "") {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "object" && !Array.isArray(value)) {
    const record = value as { name?: unknown; id?: unknown };
    const name = typeof record.name === "string" ? record.name : "";
    const id = typeof record.id === "string" ? record.id : "";
    if (name && id) {
      return `${name} (${id})`;
    }
    return name || id || "—";
  }
  return String(value);
}
