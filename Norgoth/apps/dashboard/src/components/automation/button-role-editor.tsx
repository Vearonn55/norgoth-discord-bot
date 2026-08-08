"use client";

import { CFormInput, CFormLabel } from "@coreui/react";
import { cilTrash } from "@coreui/icons";
import { DiscordRoleBadge } from "@/components/ui/discord-role-badge";
import { DiscordButtonStylePicker } from "@/components/discord/discord-button-style-picker";
import { DiscordEmojiPicker } from "@/components/discord/discord-emoji-picker";
import { AssignmentModeSelect } from "@/components/automation/assignment-mode-select";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { GuildEmojiItem } from "@/lib/discord/emoji-data";
import type { RoleMenuStyle } from "@/lib/discord/role-menu-modes";
import type { RoleMenuEntry } from "@/stores/automation-store";
import type { GuildRole } from "@/stores/guild-store";
import { roleColorStyles } from "@/lib/discord/role-color";

type ButtonRoleEditorProps = {
  entries: RoleMenuEntry[];
  rolesById: Map<string, GuildRole>;
  guildEmojis: GuildEmojiItem[];
  onUpdate: (roleId: string, patch: Partial<RoleMenuEntry>) => void;
  // Removes a single role item from the menu (per-item delete control).
  onRemove: (roleId: string) => void;
};

export function ButtonRoleEditor({
  entries,
  rolesById,
  guildEmojis,
  onUpdate,
  onRemove,
}: ButtonRoleEditorProps) {
  if (entries.length === 0) {
    return (
      <p className="mb-0 small text-body-secondary">
        Add roles above. Each becomes a Discord button.
      </p>
    );
  }

  return (
    <div className="d-flex flex-column gap-3">
      <div>
        <h4 className="h6 fw-semibold mb-1">Button settings</h4>
        <p className="mb-0 small text-body-secondary">
          Choose Discord-supported button colors. Custom RGB colors are not
          available for Discord buttons.
        </p>
      </div>
      {entries.map((entry) => {
        const role = rolesById.get(entry.role_id);
        const tint = roleColorStyles(role?.color);
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
            <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
              <DiscordRoleBadge
                name={role?.name ?? entry.label}
                color={role?.color}
              />
              <Button
                variant="danger"
                size="sm"
                onClick={() => onRemove(entry.role_id)}
                aria-label={`Remove ${role?.name ?? entry.label}`}
              >
                <Icon icon={cilTrash} />
              </Button>
            </div>
            <div className="row g-3">
              <div className="col-md-4">
                <CFormLabel className="small">Button label</CFormLabel>
                <CFormInput
                  value={entry.label}
                  onChange={(e) =>
                    onUpdate(entry.role_id, { label: e.target.value })
                  }
                  maxLength={80}
                />
              </div>
              <div className="col-md-4">
                <CFormLabel className="small">Button emoji</CFormLabel>
                <DiscordEmojiPicker
                  value={entry.emoji ?? ""}
                  onChange={(emoji) => onUpdate(entry.role_id, { emoji })}
                  guildEmojis={guildEmojis}
                />
              </div>
              <div className="col-md-4">
                <AssignmentModeSelect
                  value={entry.mode ?? "toggle"}
                  onChange={(mode) => onUpdate(entry.role_id, { mode })}
                />
              </div>
              <div className="col-12">
                <CFormLabel className="small">Button color</CFormLabel>
                <DiscordButtonStylePicker
                  value={(entry.style as RoleMenuStyle) ?? "secondary"}
                  onChange={(style) => onUpdate(entry.role_id, { style })}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
