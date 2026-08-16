"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { CFormInput } from "@coreui/react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import { Button } from "@/components/ui/button";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";

export type SenderStylesPanelHandle = {
  save: () => Promise<boolean>;
  dirty: boolean;
};

type SenderStylesPanelProps = {
  onDirtyChange?: (dirty: boolean) => void;
};

export const SenderStylesPanel = forwardRef<
  SenderStylesPanelHandle,
  SenderStylesPanelProps
>(function SenderStylesPanel({ onDirtyChange }, ref) {
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

  const dirty = displayName.trim() !== "" || avatarUrl.trim() !== "";

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const save = useCallback(async () => {
    if (!guildId || !displayName.trim()) return false;
    await createStyle(guildId, {
      display_name: displayName.trim(),
      avatar_url: avatarUrl.trim() || null,
    });
    setDisplayName("");
    setAvatarUrl("");
    return true;
  }, [avatarUrl, createStyle, displayName, guildId]);

  useImperativeHandle(ref, () => ({ save, dirty }), [dirty, save]);

  return (
    <div className="d-flex flex-column gap-4">
      <p className="small text-body-secondary mb-0">{copy.stylesIntro}</p>
      <div className="d-flex flex-column gap-3">
        <div>
          <label className="form-label small" htmlFor="cn-style-name">
            {copy.displayName}
          </label>
          <CFormInput
            id="cn-style-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </div>
        <div>
          <label className="form-label small" htmlFor="cn-style-avatar">
            {copy.avatarUrl}
          </label>
          <CFormInput
            id="cn-style-avatar"
            value={avatarUrl}
            onChange={(e) => setAvatarUrl(e.target.value)}
          />
        </div>
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
});
