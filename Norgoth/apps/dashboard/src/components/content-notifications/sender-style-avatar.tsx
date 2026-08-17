"use client";

import { useEffect, useState } from "react";

export function isPublicHttpsAvatarUrl(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed) return true;
  if (trimmed.length > 500) return false;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "https:") return false;
    if (parsed.username || parsed.password) return false;
    const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
    if (!host || host === "localhost") return false;
    if (host === "127.0.0.1" || host === "::1" || host === "0.0.0.0") return false;
    if (/^(10\.|192\.168\.|169\.254\.)/.test(host)) return false;
    if (/^172\.(1[6-9]|2\d|3[0-1])\./.test(host)) return false;
    return true;
  } catch {
    return false;
  }
}

export function senderStyleFallbackLabel(displayName: string): string {
  const trimmed = displayName.trim();
  return trimmed ? trimmed[0]!.toUpperCase() : "?";
}

type SenderStyleAvatarProps = {
  src: string | null | undefined;
  displayName: string;
  size?: number;
  onImageError?: () => void;
};

export function SenderStyleAvatar({
  src,
  displayName,
  size = 36,
  onImageError,
}: SenderStyleAvatarProps) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  const trimmed = (src || "").trim();
  const syntacticallyOk = Boolean(trimmed) && isPublicHttpsAvatarUrl(trimmed);
  const showImage = syntacticallyOk && !failed;
  const label = senderStyleFallbackLabel(displayName);

  if (!showImage) {
    return (
      <div
        className="rounded-circle d-flex align-items-center justify-content-center fw-semibold text-uppercase bg-secondary text-white flex-shrink-0"
        style={{ width: size, height: size, fontSize: size * 0.4 }}
        aria-label={displayName}
        title={displayName}
      >
        {label}
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={trimmed}
      alt={displayName}
      width={size}
      height={size}
      className="rounded-circle flex-shrink-0"
      style={{ objectFit: "cover", width: size, height: size }}
      referrerPolicy="no-referrer"
      onError={() => {
        setFailed(true);
        onImageError?.();
      }}
    />
  );
}

