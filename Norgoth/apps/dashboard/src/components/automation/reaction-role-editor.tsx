"use client";

import { cilTrash } from "@coreui/icons";
import { DiscordRoleBadge } from "@/components/ui/discord-role-badge";
import { DiscordEmojiPicker } from "@/components/discord/discord-emoji-picker";
import { AssignmentModeSelect } from "@/components/automation/assignment-mode-select";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { GuildEmojiItem } from "@/lib/discord/emoji-data";
import type { RoleMenuEntry } from "@/stores/automation-store";
import type { GuildRole } from "@/stores/guild-store";
import { roleColorStyles } from "@/lib/discord/role-color";

type ReactionRoleEditorProps = {
  entries: RoleMenuEntry[];
  rolesById: Map<string, GuildRole>;
  guildEmojis: GuildEmojiItem[];
  onUpdate: (roleId: string, patch: Partial<RoleMenuEntry>) => void;
  // Removes a single role item from the menu (per-item delete control).
  onRemove: (roleId: string) => void;
};

export function ReactionRoleEditor({
  entries,
  rolesById,
  guildEmojis,
  onUpdate,
  onRemove,
}: ReactionRoleEditorProps) {
  if (entries.length === 0) {
    return (
      <p className="mb-0 small text-body-secondary">
        Add roles above. Each needs an emoji reaction members can click.
      </p>
    );
  }

  return (
    <div className="d-flex flex-column gap-3">
      <div>
        <h4 className="h6 fw-semibold mb-1">Emoji reaction settings</h4>
        <p className="mb-0 small text-body-secondary">
          After publishing, the bot adds these reactions to the message. Each
          emoji must be unique for this menu.
        </p>
      </div>
      {entries.map((entry) => {
        const role = rolesById.get(entry.role_id);
        const tint = roleColorStyles(role?.color);
        const missingEmoji = !(entry.emoji ?? "").trim();
        return (
          <div
            key={entry.role_id}
            className="border rounded p-3"
            style={
              tint
                ? { borderLeft: `3px solid ${tint.borderColor}` }
                : undefined
            }
          >
            <div className="row g-3 align-items-start">
              <div className="col-md-3">
                <DiscordRoleBadge
                  name={role?.name ?? entry.label}
                  color={role?.color}
                />
              </div>
              <div className="col-md-5">
                <div className="small mb-1 fw-semibold">Reaction emoji</div>
                <DiscordEmojiPicker
                  value={entry.emoji ?? ""}
                  onChange={(emoji) => onUpdate(entry.role_id, { emoji })}
                  guildEmojis={guildEmojis}
                  required
                />
                {missingEmoji ? (
                  <p className="mb-0 mt-1 small text-warning">
                    Choose an emoji before publishing.
                  </p>
                ) : null}
              </div>
              <div className="col-md-3">
                <AssignmentModeSelect
                  value={entry.mode ?? "toggle"}
                  onChange={(mode) => onUpdate(entry.role_id, { mode })}
                />
              </div>
              <div className="col-md-1 d-flex align-items-start justify-content-end">
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => onRemove(entry.role_id)}
                  aria-label={`Remove ${role?.name ?? entry.label}`}
                >
                  <Icon icon={cilTrash} />
                </Button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
