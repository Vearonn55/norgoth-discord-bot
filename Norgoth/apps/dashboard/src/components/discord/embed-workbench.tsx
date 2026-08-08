"use client";

import type { ReactNode } from "react";

type EmbedWorkbenchProps = {
  /** Configuration fields (left column on desktop). */
  editor: ReactNode;
  /** Live Discord-style preview (right column on desktop). */
  preview: ReactNode;
  editorLabel?: string;
  previewLabel?: string;
  className?: string;
};

/**
 * Shared two-column editor + live-preview layout used by every embed workflow
 * (level-up, campaigns, honeypot, embed messages, welcome/leave). On desktop
 * the configuration sits on the left and a sticky preview on the right; on
 * narrow screens they stack vertically so the preview stays close to the form.
 */
export function EmbedWorkbench({
  editor,
  preview,
  editorLabel,
  previewLabel = "Live preview",
  className,
}: EmbedWorkbenchProps) {
  return (
    <div className={["row g-4", className].filter(Boolean).join(" ")}>
      <div className="col-12 col-xl-7">
        {editorLabel ? (
          <div className="small text-uppercase fw-semibold text-body-secondary mb-2">
            {editorLabel}
          </div>
        ) : null}
        {editor}
      </div>
      <div className="col-12 col-xl-5">
        <div className="norgoth-embed-workbench-preview">
          {previewLabel ? (
            <div className="small text-uppercase fw-semibold text-body-secondary mb-2">
              {previewLabel}
            </div>
          ) : null}
          {preview}
        </div>
      </div>
    </div>
  );
}
