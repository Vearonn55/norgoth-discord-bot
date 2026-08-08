"use client";

import { CFormInput, CFormLabel } from "@coreui/react";
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

type DropdownRoleEditorProps = {
  entries: RoleMenuEntry[];
  rolesById: Map<string, GuildRole>;
  guildEmojis: GuildEmojiItem[];
  onUpdate: (roleId: string, patch: Partial<RoleMenuEntry>) => void;
  onRemove: (roleId: string) => void;
};

export function DropdownRoleEditor({
  entries,
  rolesById,
  guildEmojis,
  onUpdate,
  onRemove,
}: DropdownRoleEditorProps) {
  if (entries.length === 0) {
    return (
      <p className="mb-0 small text-body-secondary">
        Add roles above. Each becomes an option in the dropdown list.
      </p>
    );
  }

  return (
    <div className="d-flex flex-column gap-3">
      <div>
        <h4 className="h6 fw-semibold mb-1">Dropdown List options</h4>
        <p className="mb-0 small text-body-secondary">
          Members will pick one option from the list. Placeholder and multi-select
          limits are fixed by Discord publish defaults for now.
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
            <div className="row g-3 align-items-start">
              <div className="col-md-3">
                <DiscordRoleBadge
                  name={role?.name ?? entry.label}
                  color={role?.color}
                />
              </div>
              <div className="col-md-3">
                <CFormLabel className="small">Option label</CFormLabel>
                <CFormInput
                  value={entry.label}
                  onChange={(e) =>
                    onUpdate(entry.role_id, { label: e.target.value })
                  }
                  maxLength={80}
                />
              </div>
              <div className="col-md-3">
                <CFormLabel className="small">Option emoji</CFormLabel>
                <DiscordEmojiPicker
                  value={entry.emoji ?? ""}
                  onChange={(emoji) => onUpdate(entry.role_id, { emoji })}
                  guildEmojis={guildEmojis}
                />
              </div>
              <div className="col-md-2">
                <AssignmentModeSelect
                  value={entry.mode ?? "toggle"}
                  onChange={(mode) => onUpdate(entry.role_id, { mode })}
                />
              </div>
              <div className="col-md-1 d-flex align-items-end justify-content-end h-100">
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
