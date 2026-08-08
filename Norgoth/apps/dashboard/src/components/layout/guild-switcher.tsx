"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CDropdown, CDropdownToggle, CDropdownMenu, CDropdownItem } from "@coreui/react";
import { apiUrl } from "@/lib/api";
import { useGuildStore, type SelectedGuild } from "@/stores/guild-store";

type ServerItem = {
  id: string;
  name: string;
  icon_url: string | null;
  bot_installed: boolean;
};

export function GuildSwitcher() {
  const params = useParams();
  const lang = String(params?.lang ?? "en");
  const router = useRouter();
  const selectedGuild = useGuildStore((s) => s.selectedGuild);
  const selectGuild = useGuildStore((s) => s.selectGuild);
  const clearGuild = useGuildStore((s) => s.clearGuild);
  const [servers, setServers] = useState<ServerItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(apiUrl("/api/v1/sessions/servers"), {
          cache: "no-store",
          credentials: "include",
        });
        if (!response.ok) return;
        const data = (await response.json()) as { servers: ServerItem[] };
        if (!cancelled) {
          setServers((data.servers ?? []).filter((s) => s.bot_installed));
        }
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSelect(server: ServerItem) {
    clearGuild();
    const guild: SelectedGuild = {
      id: server.id,
      name: server.name,
      icon_url: server.icon_url,
      bot_installed: true,
    };
    await selectGuild(guild);
    router.refresh();
  }

  const label = selectedGuild?.name ?? "Select server";

  return (
    <CDropdown>
      <CDropdownToggle color="secondary" size="sm" caret>
        {selectedGuild?.icon_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={selectedGuild.icon_url}
            alt=""
            width={18}
            height={18}
            className="rounded-circle me-2"
          />
        ) : null}
        {label}
      </CDropdownToggle>
      <CDropdownMenu>
        {servers.map((server) => (
          <CDropdownItem
            key={server.id}
            active={server.id === selectedGuild?.id}
            onClick={() => onSelect(server)}
          >
            {server.name}
          </CDropdownItem>
        ))}
        <CDropdownItem onClick={() => router.push(`/${lang}/servers`)}>
          All servers…
        </CDropdownItem>
      </CDropdownMenu>
    </CDropdown>
  );
}
