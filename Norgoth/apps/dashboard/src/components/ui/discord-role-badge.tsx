"use client";

import type { ReactNode } from "react";
import {
  normalizeDiscordRoleColor,
  roleColorStyles,
} from "@/lib/discord/role-color";

type DiscordRoleBadgeProps = {
  name: string;
  color?: string | number | null;
  className?: string;
  children?: ReactNode;
};

export function DiscordRoleBadge({
  name,
  color,
  className,
  children,
}: DiscordRoleBadgeProps) {
  const styles = roleColorStyles(color);
  const hex = normalizeDiscordRoleColor(color);

  return (
    <span
      className={["norgoth-discord-role-badge", className]
        .filter(Boolean)
        .join(" ")}
      style={
        styles
          ? {
              background: styles.background,
              color: styles.color,
              borderColor: styles.borderColor,
            }
          : undefined
      }
      title={hex ? `${name} (${hex})` : name}
    >
      <span
        className="norgoth-discord-role-dot"
        style={{ background: hex ?? "rgba(241,244,250,0.45)" }}
        aria-hidden
      />
      @{name}
      {children}
    </span>
  );
}
