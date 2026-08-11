"use client";

import { useRef, useState } from "react";
import { CFormInput, CFormLabel } from "@coreui/react";
import { Button } from "@/components/ui/button";
import {
  ACCEPTED_IMAGE_TYPES,
  useImageUpload,
} from "@/hooks/use-image-upload";
import { EmbedImagePlaceholder } from "@/components/discord/embed-image-placeholder";

type EmbedMediaPickerProps = {
  label: string;
  helper?: string;
  value: string;
  onChange: (url: string) => void;
  guildId?: string;
  banner?: boolean;
  /**
   * Render a banner slot's card at the compact thumbnail height so a
   * thumbnail + banner pair line up visually. The stored value and Discord
   * media semantics are unchanged; the preview uses `object-fit: contain` so
   * wide images are letterboxed rather than distorted.
   */
  equalizeToThumbnail?: boolean;
};

/**
 * Reusable embed media control: accepts either a local PC upload or an image
 * URL, shows a preview with replace/remove, and reports loading/error state.
 */
export function EmbedMediaPicker({
  label,
  helper,
  value,
  onChange,
  guildId,
  banner = false,
  equalizeToThumbnail = false,
}: EmbedMediaPickerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [showUrl, setShowUrl] = useState(false);
  const { upload, uploading, error, clearError } = useImageUpload(guildId);

  const openChooser = () => {
    clearError();
    inputRef.current?.click();
  };

  const handleFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const url = await upload(file);
    if (url) {
      onChange(url);
      setShowUrl(false);
    }
  };

  return (
    <div className="d-flex flex-column gap-2">
      <CFormLabel className="mb-0">{label}</CFormLabel>
      {helper ? (
        <div className="small text-body-tertiary">{helper}</div>
      ) : null}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_IMAGE_TYPES.join(",")}
        className="d-none"
        onChange={handleFile}
      />

      {value ? (
        <div className="d-flex flex-column gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={value}
            alt={label}
            className="rounded border"
            style={
              equalizeToThumbnail
                ? {
                    width: "100%",
                    height: 96,
                    maxHeight: 96,
                    objectFit: "contain",
                  }
                : {
                    width: banner ? "100%" : 96,
                    height: banner ? "auto" : 96,
                    maxHeight: banner ? 180 : 96,
                    objectFit: "cover",
                  }
            }
          />
          <div className="d-flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={openChooser}
              disabled={uploading || !guildId}
            >
              {uploading ? "Uploading…" : "Replace"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onChange("")}
              disabled={uploading}
            >
              Remove
            </Button>
          </div>
        </div>
      ) : (
        <EmbedImagePlaceholder
          label={label}
          banner={banner}
          equalizeToThumbnail={equalizeToThumbnail}
          onClick={openChooser}
        />
      )}

      <div className="d-flex align-items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowUrl((prev) => !prev)}
        >
          {showUrl ? "Hide URL" : "Use image URL"}
        </Button>
        {!guildId ? (
          <span className="small text-body-tertiary">
            Select a server to upload files
          </span>
        ) : null}
      </div>

      {showUrl ? (
        <CFormInput
          value={value}
          placeholder="https://…"
          onChange={(event) => onChange(event.target.value)}
          aria-label={`${label} URL`}
        />
      ) : null}

      {error ? (
        <div className="small text-danger">{error}</div>
      ) : null}
    </div>
  );
}
