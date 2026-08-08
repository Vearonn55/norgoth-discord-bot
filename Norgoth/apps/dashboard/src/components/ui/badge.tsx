"use client";

import { CBadge } from "@coreui/react";
import type { ReactNode } from "react";

type BadgeVariant = "neutral" | "success" | "warning" | "danger" | "info";

type BadgeProps = {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
};

const colorMap: Record<BadgeVariant, string> = {
  neutral: "dark",
  success: "success",
  warning: "warning",
  danger: "danger",
  info: "info",
};

export function Badge({
  children,
  variant = "neutral",
  className,
}: BadgeProps) {
  return (
    <CBadge
      color={colorMap[variant]}
      className={["px-2 py-1", className].filter(Boolean).join(" ")}
    >
      {children}
    </CBadge>
  );
}
