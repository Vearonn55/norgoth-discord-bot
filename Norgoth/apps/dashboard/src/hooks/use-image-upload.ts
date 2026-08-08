"use client";

import { useCallback, useState } from "react";
import { apiUrl } from "@/lib/api";

export const ACCEPTED_IMAGE_TYPES = [
  "image/png",
  "image/jpeg",
  "image/gif",
  "image/webp",
];

export const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

type UploadResult = {
  id: string;
  url: string;
  mime_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
};

/**
 * Upload an image file to the guild-scoped upload endpoint. Performs a light
 * client-side pre-check; the server remains the source of truth for validation.
 */
export function useImageUpload(guildId: string | undefined) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(
    async (file: File): Promise<string | null> => {
      setError(null);

      if (!guildId) {
        setError("No server selected.");
        return null;
      }
      if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
        setError("Unsupported image type. Use PNG, JPEG, GIF, or WEBP.");
        return null;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        setError("Image exceeds the 8 MB limit.");
        return null;
      }

      const form = new FormData();
      form.append("file", file);

      setUploading(true);
      try {
        const response = await fetch(
          apiUrl(`/guilds/${guildId}/uploads/image`),
          { method: "POST", body: form }
        );
        if (!response.ok) {
          let message = "Upload failed.";
          try {
            const body = await response.json();
            if (typeof body?.detail === "string") message = body.detail;
          } catch {
            // Ignore JSON parse failures; keep the generic message.
          }
          setError(message);
          return null;
        }
        const result = (await response.json()) as UploadResult;
        return result.url;
      } catch {
        setError("Network error during upload.");
        return null;
      } finally {
        setUploading(false);
      }
    },
    [guildId]
  );

  return { upload, uploading, error, clearError: () => setError(null) };
}
