"use client";

import { useEffect, useState } from "react";
import { CFormInput, CFormTextarea } from "@coreui/react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useContentNotificationsStore } from "@/stores/content-notifications-store";
import { Button } from "@/components/ui/button";
import { useContentNotificationsCopy } from "@/lib/content-notifications-copy";

export function TemplatesPanel() {
  const copy = useContentNotificationsCopy();
  const { guildId } = useFirstGuild();
  const templates = useContentNotificationsStore((s) => s.templates);
  const loadTemplates = useContentNotificationsStore((s) => s.loadTemplates);
  const createTemplate = useContentNotificationsStore((s) => s.createTemplate);
  const deleteTemplate = useContentNotificationsStore((s) => s.deleteTemplate);
  const [name, setName] = useState("");
  const [content, setContent] = useState(
    "{ping_role}\n{account} posted new content!\n\n{title}\n{link}"
  );

  useEffect(() => {
    if (guildId) void loadTemplates(guildId);
  }, [guildId, loadTemplates]);

  return (
    <div className="d-flex flex-column gap-4">
      <p className="small text-body-secondary mb-0">{copy.templatesIntro}</p>

      <div className="border rounded p-3 d-flex flex-column gap-3">
        <div>
          <label className="form-label small">{copy.templateName}</label>
          <CFormInput
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className="form-label small">{copy.templateContent}</label>
          <CFormTextarea
            rows={5}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </div>
        <div className="small text-body-secondary">
          {copy.templateTags} {"{account}"} {"{title}"} {"{link}"}{" "}
          {"{playable_link}"} {"{ping_role}"} {"{game}"} {"{viewers}"}{" "}
          {"{platform_icon}"} {"{profile_pic}"}
        </div>
        <Button
          type="button"
          disabled={!guildId || !name.trim()}
          onClick={() => {
            if (!guildId) return;
            void createTemplate(guildId, {
              name: name.trim(),
              content,
            }).then(() => {
              setName("");
            });
          }}
        >
          {copy.createTemplate}
        </Button>
      </div>

      <div className="d-flex flex-column gap-2">
        {templates.map((template) => (
          <div
            key={template.id}
            className="border rounded p-3 d-flex justify-content-between gap-3"
          >
            <div>
              <div className="fw-semibold">{template.name}</div>
              <pre className="small text-body-secondary mb-0 mt-2">
                {template.content}
              </pre>
            </div>
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={() =>
                guildId && void deleteTemplate(guildId, template.id)
              }
            >
              {copy.delete}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
