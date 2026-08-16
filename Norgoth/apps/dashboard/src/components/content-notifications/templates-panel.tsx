"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { CCol, CFormInput, CFormSelect, CFormTextarea, CRow } from "@coreui/react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import { Button } from "@/components/ui/button";
import { MessagePreview } from "@/components/discord/message-preview";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";

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
  const loadTemplates = useContentNotificationsStore((s) => s.loadTemplates);
  const createTemplate = useContentNotificationsStore((s) => s.createTemplate);
  const updateTemplate = useContentNotificationsStore((s) => s.updateTemplate);
  const deleteTemplate = useContentNotificationsStore((s) => s.deleteTemplate);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [platformDefault, setPlatformDefault] = useState("");
  const [content, setContent] = useState(DEFAULT_CONTENT);

  useEffect(() => {
    if (guildId) void loadTemplates(guildId);
  }, [guildId, loadTemplates]);

  const dirty =
    name.trim() !== "" ||
    content !== DEFAULT_CONTENT ||
    platformDefault !== "" ||
    editingId !== null;

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  function resetForm() {
    setEditingId(null);
    setName("");
    setPlatformDefault("");
    setContent(DEFAULT_CONTENT);
  }

  const save = useCallback(async () => {
    if (!guildId || !name.trim()) return false;
    const payload = {
      name: name.trim(),
      content,
      platform_default_for: platformDefault || null,
    };
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
    return true;
  }, [
    content,
    createTemplate,
    editingId,
    guildId,
    name,
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
            className="border rounded p-3 d-flex justify-content-between gap-3"
          >
            <button
              type="button"
              className="btn btn-link text-start text-decoration-none p-0"
              onClick={() => {
                setEditingId(template.id);
                setName(template.name);
                setPlatformDefault(template.platform_default_for ?? "");
                setContent(template.content);
              }}
            >
              <div className="fw-semibold">{template.name}</div>
              <pre className="small text-body-secondary mb-0 mt-2">
                {template.content}
              </pre>
            </button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={() => {
                if (!guildId) return;
                void deleteTemplate(guildId, template.id).then(() => {
                  if (editingId === template.id) resetForm();
                });
              }}
            >
              {copy.delete}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
});
