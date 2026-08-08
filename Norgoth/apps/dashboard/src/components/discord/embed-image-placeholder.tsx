"use client";

type EmbedImagePlaceholderProps = {
  label: string;
  banner?: boolean;
  onClick: () => void;
};

/**
 * Clickable placeholder shown where embed media will appear. Opens the OS file
 * chooser (or URL entry) via the supplied handler.
 */
export function EmbedImagePlaceholder({
  label,
  banner = false,
  onClick,
}: EmbedImagePlaceholderProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="norgoth-embed-placeholder btn btn-outline-secondary border-dashed d-flex flex-column align-items-center justify-content-center text-body-secondary w-100"
      style={{ minHeight: banner ? 96 : 72 }}
      title={`Add ${label.toLowerCase()}`}
    >
      <span className="small fw-semibold">{label}</span>
      <span className="text-body-tertiary" style={{ fontSize: 11 }}>
        Click to upload or use image URL
      </span>
    </button>
  );
}
