"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CAlert,
  CButton,
  CFormCheck,
  CFormInput,
  CPagination,
  CPaginationItem,
  CSpinner,
} from "@coreui/react";
import { cilCheck } from "@coreui/icons";
import { Icon } from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

const PAGE_SIZE = 10;

type Member = {
  id: string;
  name: string;
  display_name?: string;
  avatar_url?: string;
  bot?: boolean;
};

type PaginationMeta = {
  offset: number;
  limit: number;
  total: number;
  total_pages: number;
  page: number;
  has_previous: boolean;
  has_next: boolean;
};

type ExemptMembersPickerProps = {
  guildId: string | null;
  values: string[];
  onChange: (values: string[]) => void;
};

function dedupeIds(values: string[]): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const value of values) {
    const trimmed = value.trim();
    if (!trimmed || seen.has(trimmed)) continue;
    seen.add(trimmed);
    next.push(trimmed);
  }
  return next;
}

export function ExemptMembersPicker({
  guildId,
  values,
  onChange,
}: ExemptMembersPickerProps) {
  const dict = useLocaleDict();
  const d = dict.honeypotPage;
  const [members, setMembers] = useState<Member[]>([]);
  const [memberCache, setMemberCache] = useState<Map<string, Member>>(
    () => new Map()
  );
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [exemptOnly, setExemptOnly] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedIds = useMemo(() => dedupeIds(values), [values]);
  const selectedIdsKey = selectedIds.join(",");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setPage(1);
  }, [debouncedQuery, exemptOnly, guildId]);

  const loadMembers = useCallback(async () => {
    if (!guildId) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        offset: String((page - 1) * PAGE_SIZE),
        limit: String(PAGE_SIZE),
        exclude_bots: "true",
      });
      if (debouncedQuery) params.set("q", debouncedQuery);
      if (selectedIds.length > 0) {
        params.set("include_member_ids", selectedIds.join(","));
      }
      if (exemptOnly) params.set("exempt_only", "true");

      const response = await fetch(
        apiUrl(`/guilds/${guildId}/members?${params.toString()}`),
        {
          cache: "no-store",
          credentials: "include",
        }
      );

      if (response.status === 404) {
        setMembers([]);
        setPagination(null);
        setError(d.membersSnapshotMissing);
        return;
      }

      if (!response.ok) {
        setMembers([]);
        setPagination(null);
        setError(d.membersLoadFailed);
        return;
      }

      const data = (await response.json()) as {
        members?: Member[];
        included_members?: Member[];
        pagination?: PaginationMeta;
      };
      const pageMembers = data.members ?? [];
      const includedMembers = data.included_members ?? [];
      setMembers(pageMembers);
      setPagination(data.pagination ?? null);
      setMemberCache((prev) => {
        const next = new Map(prev);
        for (const member of [...pageMembers, ...includedMembers]) {
          next.set(member.id, member);
        }
        return next;
      });
    } catch {
      setMembers([]);
      setPagination(null);
      setError(d.membersLoadFailed);
    } finally {
      setLoading(false);
    }
  }, [
    guildId,
    page,
    debouncedQuery,
    exemptOnly,
    selectedIdsKey,
    d.membersLoadFailed,
    d.membersSnapshotMissing,
  ]);

  useEffect(() => {
    void loadMembers();
  }, [loadMembers]);

  function memberLabel(member: Member | undefined, fallbackId: string): string {
    return member?.display_name || member?.name || fallbackId;
  }

  function toggleMember(memberId: string) {
    const member = memberCache.get(memberId);
    const label = memberLabel(member, memberId);
    if (selectedIds.includes(memberId)) {
      onChange(selectedIds.filter((id) => id !== memberId));
      setAnnouncement(formatDict(d.exemptSelectionRemoved, { name: label }));
      return;
    }
    onChange(dedupeIds([...selectedIds, memberId]));
    setAnnouncement(formatDict(d.exemptSelectionAdded, { name: label }));
  }

  function removeMember(memberId: string) {
    const member = memberCache.get(memberId);
    const label = memberLabel(member, memberId);
    onChange(selectedIds.filter((id) => id !== memberId));
    setAnnouncement(formatDict(d.exemptSelectionRemoved, { name: label }));
  }

  const totalPages = pagination?.total_pages ?? 1;
  const safePage = pagination?.page ?? page;
  const totalCount = pagination?.total ?? 0;
  const rangeStart =
    totalCount === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const rangeEnd =
    totalCount === 0
      ? 0
      : Math.min(safePage * PAGE_SIZE, totalCount);
  const emptyMessage =
    debouncedQuery.length > 0 ? d.membersNoResults : d.membersEmpty;

  return (
    <div className="d-flex flex-column gap-3">
      <div>
        <div className="fw-semibold mb-2">
          {formatDict(d.currentlyExemptTitle, { count: selectedIds.length })}
        </div>
        {selectedIds.length === 0 ? (
          <p className="small text-body-secondary mb-0">{d.currentlyExemptEmpty}</p>
        ) : (
          <ul className="list-unstyled mb-0 d-flex flex-column gap-2">
            {selectedIds.map((memberId) => {
              const member = memberCache.get(memberId);
              const resolved = Boolean(member && !member.bot);
              return (
                <li
                  key={memberId}
                  className="d-flex align-items-center gap-2 border rounded p-2"
                >
                  {resolved ? (
                    <>
                      {member?.avatar_url ? (
                        <img
                          src={member.avatar_url}
                          alt=""
                          width={32}
                          height={32}
                          className="rounded-circle flex-shrink-0"
                        />
                      ) : (
                        <span
                          className="rounded-circle bg-secondary flex-shrink-0"
                          style={{ width: 32, height: 32 }}
                          aria-hidden
                        />
                      )}
                      <span className="min-w-0 flex-grow-1">
                        <span className="d-block text-truncate">
                          {memberLabel(member, memberId)}
                        </span>
                        <span className="small text-body-secondary font-monospace text-break">
                          {memberId}
                        </span>
                      </span>
                    </>
                  ) : (
                    <span className="min-w-0 flex-grow-1">
                      <span className="d-block">{d.unavailableMember}</span>
                      <span className="small text-body-secondary">
                        {d.unavailableMemberHint}
                      </span>
                      <span className="small d-block font-monospace text-break">
                        {memberId}
                      </span>
                    </span>
                  )}
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-danger flex-shrink-0"
                    onClick={() => removeMember(memberId)}
                    aria-label={formatDict(d.removeExemptMember, {
                      name: memberLabel(member, memberId),
                    })}
                  >
                    {d.remove}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="d-flex flex-column gap-2">
        <CFormInput
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={d.searchMembersPlaceholder}
          aria-label={d.searchMembersPlaceholder}
        />
        <CFormCheck
          id="honeypot-exempt-only-filter"
          label={d.exemptMembersOnlyFilter}
          checked={exemptOnly}
          onChange={(event) => setExemptOnly(event.target.checked)}
        />

        {error ? (
          <CAlert color="danger" className="mb-0 py-2 small">
            <div className="d-flex align-items-center justify-content-between gap-2">
              <span>{error}</span>
              <Button variant="secondary" size="sm" onClick={() => void loadMembers()}>
                {dict.common.retry}
              </Button>
            </div>
          </CAlert>
        ) : null}

        <div
          role="listbox"
          aria-multiselectable="true"
          aria-label={d.exemptMembers}
          aria-busy={loading}
          className="border rounded p-2 d-flex flex-column gap-1 norgoth-member-picker-list"
        >
          {loading ? (
            <div className="d-flex align-items-center justify-content-center gap-2 px-2 py-4">
              <CSpinner size="sm" />
              <span className="small text-body-secondary">{d.membersLoading}</span>
            </div>
          ) : members.length === 0 ? (
            <div className="small text-body-secondary px-2 py-3 text-center">
              {emptyMessage}
            </div>
          ) : (
            members.map((member) => {
              const selected = selectedIds.includes(member.id);
              return (
                <button
                  key={member.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`btn btn-sm text-start d-flex align-items-center gap-2 norgoth-member-row${
                    selected ? " norgoth-member-row-selected" : ""
                  }`}
                  onClick={() => toggleMember(member.id)}
                >
                  {selected ? (
                    <Icon icon={cilCheck} className="flex-shrink-0" aria-hidden />
                  ) : (
                    <span
                      className="flex-shrink-0 d-inline-block"
                      style={{ width: 16 }}
                      aria-hidden
                    />
                  )}
                  {member.avatar_url ? (
                    <img
                      src={member.avatar_url}
                      alt=""
                      width={28}
                      height={28}
                      className="rounded-circle flex-shrink-0"
                    />
                  ) : null}
                  <span className="min-w-0 flex-grow-1">
                    <span className="d-block text-truncate">
                      {memberLabel(member, member.id)}
                    </span>
                    <span className="small text-body-secondary font-monospace text-break">
                      {member.id}
                    </span>
                  </span>
                  {selected ? (
                    <span className="badge bg-primary flex-shrink-0">
                      {d.exemptBadge}
                    </span>
                  ) : null}
                </button>
              );
            })
          )}
        </div>

        {pagination && totalCount > PAGE_SIZE ? (
          <div className="d-flex align-items-center justify-content-between gap-2 norgoth-pagination-bar flex-wrap">
            <span className="small text-body-secondary">
              {formatDict(d.membersPageSummary, {
                start: rangeStart,
                end: rangeEnd,
                total: totalCount,
                selected: selectedIds.length,
              })}
            </span>
            <div className="d-flex align-items-center gap-2">
              <CButton
                color="secondary"
                variant="outline"
                size="sm"
                disabled={safePage <= 1 || loading}
                onClick={() => setPage(safePage - 1)}
              >
                {dict.serverSelector.previousPage}
              </CButton>
              <CPagination
                className="mb-0 norgoth-pagination"
                aria-label={d.membersPaginationAria}
              >
                <CPaginationItem active>
                  {safePage}/{totalPages}
                </CPaginationItem>
              </CPagination>
              <CButton
                color="secondary"
                variant="outline"
                size="sm"
                disabled={safePage >= totalPages || loading}
                onClick={() => setPage(safePage + 1)}
              >
                {dict.serverSelector.nextPage}
              </CButton>
            </div>
          </div>
        ) : pagination && totalCount > 0 ? (
          <span className="small text-body-secondary">
            {formatDict(d.membersPageSummary, {
              start: rangeStart,
              end: rangeEnd,
              total: totalCount,
              selected: selectedIds.length,
            })}
          </span>
        ) : null}

        <div aria-live="polite" className="visually-hidden">
          {announcement}
        </div>
      </div>
    </div>
  );
}
