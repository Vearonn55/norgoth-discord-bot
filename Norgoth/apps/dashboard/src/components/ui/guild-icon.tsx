"use client";

import { useEffect, useState } from "react";

function guildInitials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "?";
}

export function GuildIcon({
  url,
  name,
  size,
  className,
}: {
  url?: string | null;
  name: string;
  size: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [url]);

  const showImage = Boolean(url) && !failed;

  if (showImage && url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={`${name} server icon`}
        width={size}
        height={size}
        className={className ?? "rounded-circle flex-shrink-0"}
        style={{ objectFit: "cover", width: size, height: size }}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
      />
    );
  }

  const initials = guildInitials(name);

  return (
    <span
      className={
        className ??
        "rounded-circle flex-shrink-0 d-inline-flex align-items-center justify-content-center"
      }
      style={{
        width: size,
        height: size,
        background: "var(--cui-secondary-bg)",
        color: "var(--cui-body-color)",
        fontWeight: 700,
        fontSize: Math.max(12, Math.floor(size * 0.4)),
        letterSpacing: "0.02em",
      }}
      role="img"
      aria-label={`${name} fallback icon`}
      title={name}
    >
      {initials}
    </span>
  );
}
