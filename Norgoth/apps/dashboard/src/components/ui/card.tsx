"use client";

import { CCard, CCardBody } from "@coreui/react";
import type { ReactNode } from "react";

type CardVariant = "static" | "interactive";
export type CardLevel = "primary" | "secondary";

type CardProps = {
  children: ReactNode;
  className?: string;
  variant?: CardVariant;
  /** Aligns with SectionCard border hierarchy. Defaults to primary. */
  level?: CardLevel;
  onClick?: () => void;
};

export function Card({
  children,
  className,
  variant = "static",
  level = "primary",
  onClick,
}: CardProps) {
  const interactive = variant === "interactive";
  const classes = [
    "norgoth-card",
    level === "primary"
      ? "norgoth-section-card-primary"
      : "norgoth-section-card-secondary",
    interactive ? "norgoth-card-interactive" : "norgoth-card-static",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <CCard
      className={classes}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      <CCardBody>{children}</CCardBody>
    </CCard>
  );
}
