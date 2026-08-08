"use client";

import { useMemo, useState } from "react";
import {
  CButton,
  CFormInput,
  CPagination,
  CPaginationItem,
} from "@coreui/react";
import type { GuildChannel } from "@/stores/guild-store";

type GuildChannelMultiSelectProps = {
  channels: GuildChannel[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  maxSelected?: number;
  pageSize?: number;
  searchPlaceholder?: string;
  emptyMessage?: string;
};

/**
 * Multi-select list for Discord text channels. Mirrors RoleMultiPicker so the
 * two selectors feel identical. Selected channels appear as removable chips.
 */
export function GuildChannelMultiSelect({
  channels,
  selectedIds,
  onChange,
  maxSelected,
  pageSize = 8,
  searchPlaceholder = "Search channels…",
  emptyMessage = "No channels match.",
}: GuildChannelMultiSelectProps) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return channels.filter((channel) =>
      q ? channel.name.toLowerCase().includes(q) : true
    );
  }, [channels, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const pageChannels = filtered.slice(
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
            const channel = channels.find((c) => c.id === id);
            return (
              <CButton
                key={id}
                type="button"
                color="primary"
                size="sm"
                className="py-1"
                onClick={() => toggle(id)}
                aria-label={`Remove #${channel?.name ?? id}`}
              >
                #{channel?.name ?? id} ×
              </CButton>
            );
          })}
        </div>
      ) : null}

      <div className="border rounded p-2 d-flex flex-column gap-1 norgoth-role-picker-list">
        {pageChannels.length === 0 ? (
          <div className="small text-body-secondary px-2 py-3 text-center">
            {emptyMessage}
          </div>
        ) : (
          pageChannels.map((channel) => {
            const active = selectedIds.includes(channel.id);
            return (
              <CButton
                key={channel.id}
                type="button"
                color={active ? "primary" : "secondary"}
                variant={active ? undefined : "outline"}
                className="justify-content-start norgoth-role-picker-item"
                onClick={() => toggle(channel.id)}
              >
                #{channel.name}
                {channel.category ? (
                  <span className="ms-2 small text-body-secondary">
                    {channel.category}
                  </span>
                ) : null}
              </CButton>
            );
          })
        )}
      </div>

      {filtered.length > pageSize ? (
        <div className="d-flex align-items-center justify-content-between gap-2 norgoth-pagination-bar">
          <span className="small text-body-secondary">
            {filtered.length} channels
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
            <CPagination
              className="mb-0 norgoth-pagination"
              aria-label="Channel list pagination"
            >
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
