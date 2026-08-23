"use client";

import type { ReactNode } from "react";
import {
  discordRoleDotColor,
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
  const dotColor = discordRoleDotColor(color);

  return (
    <span
      className={["norgoth-discord-role-badge", className]
        .filter(Boolean)
        .join(" ")}
      style={{
        background: styles.background,
        color: styles.color,
        borderColor: styles.borderColor,
      }}
      title={hex ? `${name} (${hex})` : name}
    >
      <span
        className="norgoth-discord-role-dot"
        style={{ background: dotColor }}
        aria-hidden
      />
      @{name}
      {children}
    </span>
  );
}
