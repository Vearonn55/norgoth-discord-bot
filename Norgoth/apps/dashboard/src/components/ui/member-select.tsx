"use client";

import { useEffect, useMemo, useState } from "react";
import { CFormInput, CFormSelect } from "@coreui/react";
import { apiUrl } from "@/lib/api";

type Member = {
  id: string;
  name: string;
  display_name?: string;
  bot?: boolean;
};

type MemberSelectProps = {
  guildId: string | null;
  values: string[];
  onChange: (values: string[]) => void;
};

export function MemberSelect({ guildId, values, onChange }: MemberSelectProps) {
  const [members, setMembers] = useState<Member[]>([]);
  const [query, setQuery] = useState("");

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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = members.filter((m) => !m.bot);
    if (!q) return list.slice(0, 100);
    return list
      .filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          (m.display_name || "").toLowerCase().includes(q) ||
          m.id.includes(q)
      )
      .slice(0, 100);
  }, [members, query]);

  return (
    <div className="d-flex flex-column gap-2">
      <CFormInput
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search members…"
      />
      <CFormSelect
        multiple
        htmlSize={6}
        value={values}
        onChange={(e) =>
          onChange(Array.from(e.target.selectedOptions).map((o) => o.value))
        }
      >
        {filtered.map((member) => (
          <option key={member.id} value={member.id}>
            {member.display_name || member.name} ({member.id})
          </option>
        ))}
      </CFormSelect>
    </div>
  );
}
