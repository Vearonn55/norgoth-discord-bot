/**
 * Supported logging event keys the bot can emit.
 * Do not expose unsupported events in the UI.
 */

export const LOGGING_EVENT_KEYS = [
  "member.join",
  "member.leave",
  "member.nickname",
  "message.delete",
  "message.edit",
  "role.create",
  "role.delete",
  "role.update",
  "channel.create",
  "channel.delete",
  "channel.update",
] as const;

export type LoggingEventKey = (typeof LOGGING_EVENT_KEYS)[number];

export const LOGGING_EVENT_LABELS: Record<LoggingEventKey, string> = {
  "member.join": "Member joined",
  "member.leave": "Member left",
  "member.nickname": "Nickname changed",
  "message.delete": "Message deleted",
  "message.edit": "Message edited",
  "role.create": "Role created",
  "role.delete": "Role deleted",
  "role.update": "Role updated",
  "channel.create": "Channel created",
  "channel.delete": "Channel deleted",
  "channel.update": "Channel updated",
};

/** Map category + action from bot event log → event key */
export function eventKeyFromLog(
  category: string,
  action: string
): LoggingEventKey | null {
  const normalized = action.toLowerCase().replace(/\s+/g, "_");
  const candidates: Record<string, LoggingEventKey> = {
    "member.join": "member.join",
    "member.leave": "member.leave",
    "member.nickname": "member.nickname",
    "member.nickname_update": "member.nickname",
    "message.delete": "message.delete",
    "message.edit": "message.edit",
    "role.create": "role.create",
    "role.delete": "role.delete",
    "role.update": "role.update",
    "channel.create": "channel.create",
    "channel.delete": "channel.delete",
    "channel.update": "channel.update",
  };
  return (
    candidates[`${category}.${normalized}`] ??
    candidates[normalized] ??
    null
  );
}
