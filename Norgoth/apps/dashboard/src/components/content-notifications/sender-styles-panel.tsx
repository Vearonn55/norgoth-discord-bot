"use client";

import { useEffect, useState } from "react";
import { CFormInput } from "@coreui/react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import { Button } from "@/components/ui/button";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";

export function SenderStylesPanel() {
  const copy = useContentNotificationsCopy();
  const { guildId } = useFirstGuild();
  const styles = useContentNotificationsStore((s) => s.styles);
  const loadStyles = useContentNotificationsStore((s) => s.loadStyles);
  const createStyle = useContentNotificationsStore((s) => s.createStyle);
  const deleteStyle = useContentNotificationsStore((s) => s.deleteStyle);
  const [displayName, setDisplayName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");

  useEffect(() => {
    if (guildId) void loadStyles(guildId);
  }, [guildId, loadStyles]);

  return (
    <div className="d-flex flex-column gap-4">
      <p className="small text-body-secondary mb-0">{copy.stylesIntro}</p>

      <div className="border rounded p-3 d-flex flex-column gap-3">
        <div>
          <label className="form-label small">{copy.displayName}</label>
          <CFormInput
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </div>
        <div>
          <label className="form-label small">{copy.avatarUrl}</label>
          <CFormInput
            value={avatarUrl}
            onChange={(e) => setAvatarUrl(e.target.value)}
          />
        </div>
        <Button
          type="button"
          disabled={!guildId || !displayName.trim()}
          onClick={() => {
            if (!guildId) return;
            void createStyle(guildId, {
              display_name: displayName.trim(),
              avatar_url: avatarUrl.trim() || null,
            }).then(() => {
              setDisplayName("");
              setAvatarUrl("");
            });
          }}
        >
          {copy.createStyle}
        </Button>
      </div>

      <div className="d-flex flex-column gap-2">
        {styles.map((style) => (
          <div
            key={style.id}
            className="border rounded p-3 d-flex align-items-center gap-3"
          >
            {style.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={style.avatar_url}
                alt=""
                width={36}
                height={36}
                className="rounded-circle"
              />
            ) : null}
            <div className="flex-grow-1 fw-semibold">{style.display_name}</div>
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={() => guildId && void deleteStyle(guildId, style.id)}
            >
              {copy.delete}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
