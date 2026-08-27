"use client";

import { useMemo, useRef } from "react";
import { Editor } from "@tinymce/tinymce-react";
import type { Editor as TinyMCEEditor } from "tinymce";
import { CButton } from "@coreui/react";
import {
  discordMarkdownToHtml,
  htmlToDiscordMarkdown,
} from "@/lib/discord-markdown";

type RichMessageEditorProps = {
  /** Initial content, in Discord markdown. */
  value: string;
  /** Emits Discord markdown whenever the content changes. */
  onChange: (markdown: string) => void;
  /** Template variables offered as one-click inserts (e.g. "{user_name}"). */
  variables?: string[];
  height?: number;
  placeholder?: string;
  disabled?: boolean;
};

export function RichMessageEditor({
  value,
  onChange,
  variables = [],
  height = 260,
  placeholder,
  disabled = false,
}: RichMessageEditorProps) {
  const editorRef = useRef<TinyMCEEditor | null>(null);

  // The editor manages its own state after mount; the markdown prop only
  // seeds the initial content (round-tripping every keystroke would fight
  // the caret).
  const initialHtml = useMemo(() => discordMarkdownToHtml(value), []); // eslint-disable-line react-hooks/exhaustive-deps

  function insertVariable(variable: string) {
    if (disabled) return;
    editorRef.current?.insertContent(variable);
    editorRef.current?.focus();
  }

  return (
    <div className="d-flex flex-column gap-2">
      <div className="norgoth-rich-editor border rounded">
        <Editor
          tinymceScriptSrc="/tinymce/tinymce.min.js"
          licenseKey="gpl"
          disabled={disabled}
          onInit={(_evt, editor) => {
            editorRef.current = editor;
          }}
          initialValue={initialHtml}
          onEditorChange={(html) => {
            onChange(htmlToDiscordMarkdown(html));
          }}
          init={{
            height,
            min_height: height,
            menubar: false,
            statusbar: true,
            resize: true,
            skin: "oxide-dark",
            content_css: "dark",
            placeholder,
            plugins: ["lists", "link", "autolink", "code"],
            toolbar:
              "undo redo | blocks | bold italic underline strikethrough | " +
              "link bullist numlist blockquote | code | removeformat",
            block_formats:
              "Paragraph=p; Heading 1=h1; Heading 2=h2; Heading 3=h3",
            link_default_target: "_blank",
            content_style:
              "body { background: #212529; color: #dee2e6; " +
              "font-family: var(--cui-body-font-family), system-ui, sans-serif; " +
              "font-size: 14px; }" +
              "h1 { font-size: 1.45em; font-weight: 700; margin: 0.6em 0 0.35em; }" +
              "h2 { font-size: 1.25em; font-weight: 700; margin: 0.55em 0 0.3em; }" +
              "h3 { font-size: 1.1em; font-weight: 700; margin: 0.5em 0 0.25em; }",
            branding: false,
            promotion: false,
            elementpath: false,
          }}
        />
      </div>

      {variables.length > 0 ? (
        <div className="d-flex flex-wrap gap-2">
          {variables.map((variable) => (
            <CButton
              key={variable}
              type="button"
              color="secondary"
              variant="outline"
              size="sm"
              disabled={disabled}
              onClick={() => insertVariable(variable)}
            >
              {variable}
            </CButton>
          ))}
        </div>
      ) : null}
    </div>
  );
}
