"use client";

import { useMemo, useState } from "react";
import {
  CButton,
  CFormInput,
  CPagination,
  CPaginationItem,
} from "@coreui/react";
import { DiscordRoleBadge } from "@/components/ui/discord-role-badge";
import type { GuildRole } from "@/stores/guild-store";
import { roleColorStyles } from "@/lib/discord/role-color";
import { useLocaleDict } from "@/lib/locale-dict";

type RoleMultiPickerProps = {
  roles: GuildRole[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  excludeManaged?: boolean;
  maxSelected?: number;
  pageSize?: number;
  searchPlaceholder?: string;
  emptyMessage?: string;
};

export function RoleMultiPicker({
  roles,
  selectedIds,
  onChange,
  excludeManaged = true,
  maxSelected,
  pageSize = 8,
  searchPlaceholder = "Search roles…",
  emptyMessage = "No roles match.",
}: RoleMultiPickerProps) {
  const dict = useLocaleDict();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return roles
      .filter((role) => (excludeManaged ? !role.managed : true))
      .filter((role) => (q ? role.name.toLowerCase().includes(q) : true))
      .sort((a, b) => (b.position ?? 0) - (a.position ?? 0));
  }, [roles, excludeManaged, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const pageRoles = filtered.slice(
    (safePage - 1) * pageSize,
    safePage * pageSize
  );

  function toggle(id: string) {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id));
      return;
    }
    if (maxSelected != null && selectedIds.length >= maxSelected) return;
    onChange([...selectedIds, id]);
  }

  return (
    <div className="d-flex flex-column gap-2">
      <CFormInput
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(1);
        }}
        placeholder={searchPlaceholder}
      />

      {selectedIds.length > 0 ? (
        <div className="d-flex flex-wrap gap-2">
          {selectedIds.map((id) => {
            const role = roles.find((r) => r.id === id);
            return (
              <button
                key={id}
                type="button"
                className="btn btn-sm p-0 border-0 bg-transparent"
                onClick={() => toggle(id)}
                aria-label={`Remove @${role?.name ?? id}`}
              >
                <DiscordRoleBadge
                  name={role?.name ?? dict.common.roleUnavailable}
                  color={role?.color}
                />
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="border rounded p-2 d-flex flex-column gap-1 norgoth-role-picker-list">
        {pageRoles.length === 0 ? (
          <div className="small text-body-secondary px-2 py-3 text-center">
            {emptyMessage}
          </div>
        ) : (
          pageRoles.map((role) => {
            const active = selectedIds.includes(role.id);
            const tint = roleColorStyles(role.color);
            return (
              <CButton
                key={role.id}
                type="button"
                color={active ? "primary" : "secondary"}
                variant={active ? undefined : "outline"}
                className="justify-content-start norgoth-role-picker-item"
                style={
                  !active
                    ? {
                        borderColor: tint.borderColor,
                        background: tint.background,
                      }
                    : undefined
                }
                onClick={() => toggle(role.id)}
              >
                <DiscordRoleBadge name={role.name} color={role.color} />
              </CButton>
            );
          })
        )}
      </div>

      {filtered.length > pageSize ? (
        <div className="d-flex align-items-center justify-content-between gap-2 norgoth-pagination-bar">
          <span className="small text-body-secondary">
            {filtered.length} roles
            {maxSelected != null
              ? ` · ${selectedIds.length}/${maxSelected} selected`
              : ` · ${selectedIds.length} selected`}
          </span>
          <div className="d-flex align-items-center gap-2">
            <CButton
              color="secondary"
              variant="outline"
              size="sm"
              disabled={safePage <= 1}
              onClick={() => setPage(safePage - 1)}
            >
              Previous
            </CButton>
            <CPagination className="mb-0 norgoth-pagination" aria-label="Role list pagination">
              <CPaginationItem active>
                {safePage}/{totalPages}
              </CPaginationItem>
            </CPagination>
            <CButton
              color="secondary"
              variant="outline"
              size="sm"
              disabled={safePage >= totalPages}
              onClick={() => setPage(safePage + 1)}
            >
              Next
            </CButton>
          </div>
        </div>
      ) : null}
    </div>
  );
}
