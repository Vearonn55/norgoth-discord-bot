"use client";

import { useEffect, useMemo, useState } from "react";
import { CFormCheck, CFormInput } from "@coreui/react";
import { cilCheck } from "@coreui/icons";
import { Icon } from "@/components/ui/icon";
import { apiUrl } from "@/lib/api";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

type Member = {
  id: string;
  name: string;
  display_name?: string;
  avatar_url?: string;
  bot?: boolean;
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
  const [query, setQuery] = useState("");
  const [exemptOnly, setExemptOnly] = useState(false);
  const [announcement, setAnnouncement] = useState("");

  const selectedIds = useMemo(() => dedupeIds(values), [values]);

  useEffect(() => {
    if (!guildId) return;
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(apiUrl(`/guilds/${guildId}/members`), {
          cache: "no-store",
          credentials: "include",
        });
        if (!response.ok) return;
        const data = (await response.json()) as { members?: Member[] };
        if (!cancelled) setMembers(data.members ?? []);
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [guildId]);

  const memberById = useMemo(() => {
    const map = new Map<string, Member>();
    for (const member of members) {
      map.set(member.id, member);
    }
    return map;
  }, [members]);

  const humanMembers = useMemo(
    () => members.filter((member) => !member.bot),
    [members]
  );

  const selectableMembers = useMemo(() => {
    const knownIds = new Set(humanMembers.map((member) => member.id));
    const staleRows: Member[] = selectedIds
      .filter((id) => !knownIds.has(id))
      .map((id) => ({ id, name: id }));
    return [...humanMembers, ...staleRows];
  }, [humanMembers, selectedIds]);

  const filteredMembers = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = selectableMembers;
    if (exemptOnly) {
      list = list.filter((member) => selectedIds.includes(member.id));
    }
    if (q) {
      list = list.filter(
        (member) =>
          member.name.toLowerCase().includes(q) ||
          (member.display_name || "").toLowerCase().includes(q) ||
          member.id.includes(q)
      );
    }

    const selectedSet = new Set(selectedIds);
    const selectedRows = selectableMembers.filter((member) =>
      selectedSet.has(member.id)
    );
    const remaining = list
      .filter((member) => !selectedSet.has(member.id))
      .slice(0, 100);
    const merged = [...selectedRows, ...remaining];
    const seen = new Set<string>();
    return merged.filter((member) => {
      if (seen.has(member.id)) return false;
      seen.add(member.id);
      return true;
    });
  }, [exemptOnly, query, selectableMembers, selectedIds]);

  function memberLabel(member: Member | undefined, fallbackId: string): string {
    return member?.display_name || member?.name || fallbackId;
  }

  function toggleMember(memberId: string) {
    const member = memberById.get(memberId);
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
    const member = memberById.get(memberId);
    const label = memberLabel(member, memberId);
    onChange(selectedIds.filter((id) => id !== memberId));
    setAnnouncement(formatDict(d.exemptSelectionRemoved, { name: label }));
  }

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
              const member = memberById.get(memberId);
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
        <div
          role="listbox"
          aria-multiselectable="true"
          aria-label={d.exemptMembers}
          className="border rounded p-2 d-flex flex-column gap-1 norgoth-member-picker-list"
        >
          {filteredMembers.length === 0 ? (
            <div className="small text-body-secondary px-2 py-3 text-center">
              {d.exemptMembersEmpty}
            </div>
          ) : (
            filteredMembers.map((member) => {
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
        <div aria-live="polite" className="visually-hidden">
          {announcement}
        </div>
      </div>
    </div>
  );
}
