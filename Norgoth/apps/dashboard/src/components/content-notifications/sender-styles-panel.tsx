"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { cilPencil, cilTrash } from "@coreui/icons";
import { CFormInput } from "@coreui/react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";
import { formatDict } from "@/lib/locale-dict";
import { confirmDirtyClose } from "@/lib/cn-url-state";
import {
  SenderStyleAvatar,
  isPublicHttpsAvatarUrl,
} from "@/components/content-notifications/sender-style-avatar";

export type SenderStylesPanelHandle = {
  save: () => Promise<boolean>;
  dirty: boolean;
};

type SenderStylesPanelProps = {
  onDirtyChange?: (dirty: boolean) => void;
};

function avatarStatus(
  url: string,
  copy: ReturnType<typeof useContentNotificationsCopy>,
  previewFailed: boolean,
): string | null {
  const trimmed = url.trim();
  if (!trimmed) return null;
  if (!isPublicHttpsAvatarUrl(trimmed)) return copy.avatarUrlInvalid;
  if (previewFailed) return copy.avatarPreviewFailed;
  return null;
}

export const SenderStylesPanel = forwardRef<
  SenderStylesPanelHandle,
  SenderStylesPanelProps
>(function SenderStylesPanel({ onDirtyChange }, ref) {
  const copy = useContentNotificationsCopy();
  const { guildId } = useFirstGuild();
  const styles = useContentNotificationsStore((s) => s.styles);
  const loadStyles = useContentNotificationsStore((s) => s.loadStyles);
  const createStyle = useContentNotificationsStore((s) => s.createStyle);
  const updateStyle = useContentNotificationsStore((s) => s.updateStyle);
  const deleteStyle = useContentNotificationsStore((s) => s.deleteStyle);
  const [displayName, setDisplayName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [createPreviewFailed, setCreatePreviewFailed] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editAvatar, setEditAvatar] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [editPreviewFailed, setEditPreviewFailed] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (guildId) void loadStyles(guildId);
  }, [guildId, loadStyles]);

  const editingStyle = styles.find((row) => row.id === editingId) ?? null;
  const editDirty =
    editingStyle !== null &&
    (editName.trim() !== editingStyle.display_name ||
      (editAvatar.trim() || "") !== (editingStyle.avatar_url || ""));
  const dirty =
    displayName.trim() !== "" ||
    avatarUrl.trim() !== "" ||
    (editingId !== null && editDirty);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const persistEdit = useCallback(async (): Promise<boolean> => {
    if (!guildId || !editingId || savingEdit) return false;
    if (!editName.trim()) {
      setEditError(copy.displayName);
      return false;
    }
    if (editAvatar.trim() && !isPublicHttpsAvatarUrl(editAvatar)) {
      setEditError(copy.avatarUrlInvalid);
      return false;
    }
    setSavingEdit(true);
    setEditError(null);
    try {
      await updateStyle(guildId, editingId, {
        display_name: editName.trim(),
        avatar_url: editAvatar.trim() || null,
      });
      const styleId = editingId;
      setEditingId(null);
      setEditName("");
      setEditAvatar("");
      requestAnimationFrame(() => focusEditButton(styleId));
      return true;
    } catch (err) {
      setEditError(err instanceof Error ? err.message : copy.avatarUrlInvalid);
      return false;
    } finally {
      setSavingEdit(false);
    }
  }, [
    copy.avatarUrlInvalid,
    copy.displayName,
    editAvatar,
    editName,
    editingId,
    guildId,
    savingEdit,
    updateStyle,
  ]);

  const save = useCallback(async () => {
    let savedEdit = false;
    if (editingId && editDirty) {
      savedEdit = await persistEdit();
      if (!savedEdit) return false;
    }
    if (!displayName.trim()) {
      if (savedEdit) {
        onDirtyChange?.(false);
        return true;
      }
      return false;
    }
    if (!guildId) return false;
    if (avatarUrl.trim() && !isPublicHttpsAvatarUrl(avatarUrl)) {
      setCreateError(copy.avatarUrlInvalid);
      return false;
    }
    setCreateError(null);
    try {
      await createStyle(guildId, {
        display_name: displayName.trim(),
        avatar_url: avatarUrl.trim() || null,
      });
      setDisplayName("");
      setAvatarUrl("");
      setCreatePreviewFailed(false);
      onDirtyChange?.(false);
      return true;
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : copy.avatarUrlInvalid);
      return false;
    }
  }, [
    avatarUrl,
    copy.avatarUrlInvalid,
    createStyle,
    displayName,
    editDirty,
    editingId,
    guildId,
    onDirtyChange,
    persistEdit,
  ]);

  useImperativeHandle(ref, () => ({ save, dirty }), [dirty, save]);

  function focusEditButton(styleId: string) {
    document.getElementById(`cn-style-edit-${styleId}`)?.focus();
  }

  function beginEdit(styleId: string) {
    if (editingId && editingId !== styleId && editDirty) {
      if (!confirmDirtyClose(true, copy.unsavedConfirm)) return;
    }
    const style = styles.find((row) => row.id === styleId);
    if (!style) return;
    setEditingId(style.id);
    setEditName(style.display_name);
    setEditAvatar(style.avatar_url ?? "");
    setEditError(null);
    setEditPreviewFailed(false);
    requestAnimationFrame(() => {
      document.getElementById(`cn-style-edit-name-${style.id}`)?.focus();
    });
  }

  function cancelEdit() {
    const styleId = editingId;
    setEditingId(null);
    setEditName("");
    setEditAvatar("");
    setEditError(null);
    setEditPreviewFailed(false);
    if (styleId) requestAnimationFrame(() => focusEditButton(styleId));
  }

  async function handleSaveEdit() {
    await persistEdit();
  }

  async function handleDelete(styleId: string, styleName: string) {
    if (!guildId || deletingId) return;
    const confirmed = window.confirm(
      formatDict(copy.deleteStyleConfirm, { name: styleName })
    );
    if (!confirmed) return;
    setDeletingId(styleId);
    try {
      await deleteStyle(guildId, styleId);
      if (editingId === styleId) {
        setEditingId(null);
        setEditName("");
        setEditAvatar("");
        setEditError(null);
      }
    } catch {
      // Keep the card visible; the button re-enables in finally.
    } finally {
      setDeletingId(null);
    }
  }

  const createStatus = avatarStatus(avatarUrl, copy, createPreviewFailed);

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
            onChange={(e) => {
              setAvatarUrl(e.target.value);
              setCreatePreviewFailed(false);
              setCreateError(null);
            }}
          />
          <p className="form-text mb-0">{copy.avatarUrlHelp}</p>
        </div>
        <div className="d-flex align-items-center gap-3">
          <SenderStyleAvatar
            src={
              avatarUrl.trim() && isPublicHttpsAvatarUrl(avatarUrl)
                ? avatarUrl.trim()
                : null
            }
            displayName={displayName || copy.displayName}
            size={80}
            onImageError={() => setCreatePreviewFailed(true)}
          />
          {createStatus ? (
            <p className="small text-body-secondary mb-0">{createStatus}</p>
          ) : null}
        </div>
        {createError ? (
          <p className="small text-danger mb-0" role="alert">
            {createError}
          </p>
        ) : null}
      </div>
      <div className="d-flex flex-column gap-2">
        {styles.map((style) => {
          const isEditing = editingId === style.id;
          const editStatus = isEditing
            ? avatarStatus(editAvatar, copy, editPreviewFailed)
            : null;
          return (
            <div
              key={style.id}
              className="border rounded p-3 d-flex flex-column"
            >
              <div className="d-flex align-items-center gap-3 min-w-0">
                <SenderStyleAvatar
                  src={style.avatar_url}
                  displayName={style.display_name}
                  size={36}
                />
                <div className="flex-grow-1 fw-semibold min-w-0 text-truncate">
                  {style.display_name}
                </div>
              </div>
              {isEditing ? (
                <fieldset className="mt-3 mb-0">
                  <legend className="form-label small">{copy.editStyle}</legend>
                  <div className="d-flex flex-column gap-3">
                    <div>
                      <label
                        className="form-label small"
                        htmlFor={`cn-style-edit-name-${style.id}`}
                      >
                        {copy.displayName}
                      </label>
                      <CFormInput
                        id={`cn-style-edit-name-${style.id}`}
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                      />
                    </div>
                    <div>
                      <label
                        className="form-label small"
                        htmlFor={`cn-style-edit-avatar-${style.id}`}
                      >
                        {copy.avatarUrl}
                      </label>
                      <CFormInput
                        id={`cn-style-edit-avatar-${style.id}`}
                        value={editAvatar}
                        onChange={(e) => {
                          setEditAvatar(e.target.value);
                          setEditPreviewFailed(false);
                          setEditError(null);
                        }}
                      />
                      <p className="form-text mb-0">{copy.avatarUrlHelp}</p>
                    </div>
                    <div className="d-flex align-items-center gap-3">
                      <SenderStyleAvatar
                        src={
                          editAvatar.trim() &&
                          isPublicHttpsAvatarUrl(editAvatar)
                            ? editAvatar.trim()
                            : null
                        }
                        displayName={editName || style.display_name}
                        size={80}
                        onImageError={() => setEditPreviewFailed(true)}
                      />
                      {editStatus ? (
                        <p className="small text-body-secondary mb-0">
                          {editStatus}
                        </p>
                      ) : null}
                    </div>
                    {editError ? (
                      <p className="small text-danger mb-0" role="alert">
                        {editError}
                      </p>
                    ) : null}
                    <div className="d-flex justify-content-end flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={savingEdit}
                        onClick={cancelEdit}
                      >
                        {copy.cancelEdit}
                      </Button>
                      <Button
                        type="button"
                        variant="primary"
                        size="sm"
                        disabled={savingEdit}
                        onClick={() => void handleSaveEdit()}
                      >
                        {copy.saveChanges}
                      </Button>
                    </div>
                  </div>
                </fieldset>
              ) : null}
              <div className="d-flex justify-content-end align-items-center flex-wrap gap-2 mt-3">
                <Button
                  id={`cn-style-edit-${style.id}`}
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="flex-shrink-0"
                  aria-label={formatDict(copy.editStyleAria, {
                    name: style.display_name,
                  })}
                  title={formatDict(copy.editStyleAria, {
                    name: style.display_name,
                  })}
                  onClick={() => beginEdit(style.id)}
                >
                  <Icon icon={cilPencil} />
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  className="flex-shrink-0"
                  disabled={deletingId === style.id}
                  aria-label={formatDict(copy.deleteStyleAria, {
                    name: style.display_name,
                  })}
                  title={formatDict(copy.deleteStyleAria, {
                    name: style.display_name,
                  })}
                  onClick={() =>
                    void handleDelete(style.id, style.display_name)
                  }
                >
                  <Icon icon={cilTrash} />
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});
