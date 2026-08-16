"use client";

import { useEffect, useState } from "react";

export function avatarFallbackLabel(
  displayName: string,
  platform: string,
): string {
  const trimmed = displayName.trim();
  const initial = trimmed ? trimmed[0]!.toUpperCase() : "?";
  const platformLetter = (platform.trim()[0] ?? "?").toUpperCase();
  return `${initial}${platformLetter}`;
}

type PlatformAvatarProps = {
  src: string | null | undefined;
  displayName: string;
  platform: string;
  size?: number;
};

export function PlatformAvatar({
  src,
  displayName,
  platform,
  size = 40,
}: PlatformAvatarProps) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  const showImage = Boolean(src) && !failed;
  const label = avatarFallbackLabel(displayName, platform);

  if (!showImage) {
    return (
      <div
        className="rounded-circle d-flex align-items-center justify-content-center fw-semibold text-uppercase bg-secondary text-white"
        style={{ width: size, height: size, fontSize: size * 0.32 }}
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
      src={src!}
      alt={displayName}
      width={size}
      height={size}
      className="rounded-circle"
      style={{ objectFit: "cover", width: size, height: size }}
      onError={() => setFailed(true)}
    />
  );
}
