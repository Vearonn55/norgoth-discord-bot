"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { cilTrash } from "@coreui/icons";
import { CCol, CFormInput, CFormSelect, CFormTextarea, CRow } from "@coreui/react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { MessagePreview } from "@/components/discord/message-preview";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";
import { formatDict } from "@/lib/locale-dict";
import {
  isTemplateFormDirty,
  templateFormBaseline,
} from "@/lib/cn-url-state";

const DEFAULT_CONTENT =
  "{ping_role}\n{account} posted new content!\n\n{title}\n{link}";

export type TemplatesPanelHandle = {
  save: () => Promise<boolean>;
  dirty: boolean;
};

type TemplatesPanelProps = {
  onDirtyChange?: (dirty: boolean) => void;
};

export const TemplatesPanel = forwardRef<
  TemplatesPanelHandle,
  TemplatesPanelProps
>(function TemplatesPanel({ onDirtyChange }, ref) {
  const copy = useContentNotificationsCopy();
  const { guildId } = useFirstGuild();
  const templates = useContentNotificationsStore((s) => s.templates);
  const accounts = useContentNotificationsStore((s) => s.accounts);
  const loadTemplates = useContentNotificationsStore((s) => s.loadTemplates);
  const createTemplate = useContentNotificationsStore((s) => s.createTemplate);
  const updateTemplate = useContentNotificationsStore((s) => s.updateTemplate);
  const deleteTemplate = useContentNotificationsStore((s) => s.deleteTemplate);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [platformDefault, setPlatformDefault] = useState("");
  const [content, setContent] = useState(DEFAULT_CONTENT);

  useEffect(() => {
    if (guildId) void loadTemplates(guildId);
  }, [guildId, loadTemplates]);

  const editingTemplate =
    templates.find((template) => template.id === editingId) ?? null;
  const baseline = templateFormBaseline(editingTemplate, {
    name: "",
    content: DEFAULT_CONTENT,
  });
  const dirty = isTemplateFormDirty(
    { name, content, platformDefault },
    baseline,
  );

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  function resetForm() {
    setEditingId(null);
    setName("");
    setPlatformDefault("");
    setContent(DEFAULT_CONTENT);
  }

  async function handleDelete(templateId: string, templateName: string) {
    if (!guildId || deletingId) return;
    const inUse = accounts.filter((row) => row.template_id === templateId).length;
    const confirmed = window.confirm(
      formatDict(copy.deleteTemplateConfirm, {
        name: templateName,
        count: inUse,
      })
    );
    if (!confirmed) return;
    setDeletingId(templateId);
    try {
      await deleteTemplate(guildId, templateId);
      if (editingId === templateId) resetForm();
    } catch {
      // Keep the card visible; the button re-enables in finally.
    } finally {
      setDeletingId(null);
    }
  }

  const save = useCallback(async () => {
    if (!guildId || !name.trim()) return false;
    const payload = {
      name: name.trim(),
      content,
      platform_default_for: platformDefault || null,
    };
    try {
      if (editingId) {
        const existing = templates.find((t) => t.id === editingId);
        await updateTemplate(guildId, editingId, {
          ...payload,
          embed_json: existing?.embed_json ?? null,
        });
      } else {
        await createTemplate(guildId, payload);
      }
      setEditingId(null);
      setName("");
      setPlatformDefault("");
      setContent(DEFAULT_CONTENT);
      onDirtyChange?.(false);
      return true;
    } catch {
      return false;
    }
  }, [
    content,
    createTemplate,
    editingId,
    guildId,
    name,
    onDirtyChange,
    platformDefault,
    templates,
    updateTemplate,
  ]);

  useImperativeHandle(ref, () => ({ save, dirty }), [dirty, save]);

  return (
    <div className="d-flex flex-column gap-4">
      <p className="small text-body-secondary mb-0">{copy.templatesIntro}</p>
      <CRow className="g-4">
        <CCol md={5}>
          <div>
            <label className="form-label small" htmlFor="cn-template-name">
              {copy.templateName}
            </label>
            <CFormInput
              id="cn-template-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="mt-3">
            <label className="form-label small" htmlFor="cn-template-platform">
              {copy.platform}
            </label>
            <CFormSelect
              id="cn-template-platform"
              value={platformDefault}
              onChange={(e) => setPlatformDefault(e.target.value)}
            >
              <option value="">{copy.defaultTemplate}</option>
              <option value="youtube">YouTube</option>
              <option value="twitch">Twitch</option>
              <option value="kick">Kick</option>
              <option value="x">X</option>
            </CFormSelect>
          </div>
          <div className="small text-body-secondary mt-3">
            {copy.templateTags} {"{account}"} {"{title}"} {"{link}"}{" "}
            {"{playable_link}"} {"{ping_role}"} {"{game}"} {"{viewers}"}{" "}
            {"{platform_icon}"} {"{profile_pic}"}
          </div>
        </CCol>
        <CCol md={7}>
          <label className="form-label small" htmlFor="cn-template-content">
            {copy.templateContent}
          </label>
          <CFormTextarea
            id="cn-template-content"
            rows={6}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <div className="mt-3">
            <div className="small text-body-secondary mb-2">{copy.preview}</div>
            <MessagePreview content={content} mode="text" />
          </div>
        </CCol>
      </CRow>

      <div className="d-flex flex-column gap-2">
        {templates.map((template) => (
          <div
            key={template.id}
            className="border rounded p-3 d-flex flex-column"
          >
            <button
              type="button"
              className="btn btn-link text-start text-decoration-none p-0 min-w-0"
              onClick={() => {
                setEditingId(template.id);
                setName(template.name);
                setPlatformDefault(template.platform_default_for ?? "");
                setContent(template.content);
              }}
            >
              <div className="fw-semibold">{template.name}</div>
              <pre className="small text-body-secondary mb-0 mt-2 text-break">
                {template.content}
              </pre>
            </button>
            <div className="d-flex justify-content-end align-items-center flex-wrap gap-2 mt-3">
              <Button
                type="button"
                variant="danger"
                size="sm"
                className="flex-shrink-0"
                disabled={deletingId === template.id}
                aria-label={formatDict(copy.deleteTemplateAria, {
                  name: template.name,
                })}
                title={formatDict(copy.deleteTemplateAria, {
                  name: template.name,
                })}
                onClick={() => void handleDelete(template.id, template.name)}
              >
                <Icon icon={cilTrash} />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});
