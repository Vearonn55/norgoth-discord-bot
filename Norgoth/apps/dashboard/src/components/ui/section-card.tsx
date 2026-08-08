"use client";

import type { ReactNode } from "react";
import { CCard, CCardBody, CCardHeader } from "@coreui/react";
import type { NorgothCategory } from "@/lib/design/category";
import { categoryAccent } from "@/lib/design/category";

export type SectionCardLevel = "primary" | "secondary";

type SectionCardProps = {
  children: ReactNode;
  className?: string;
  level?: SectionCardLevel;
  header?: ReactNode;
  category?: NorgothCategory;
  interactive?: boolean;
  onClick?: () => void;
};

export function SectionCard({
  children,
  className,
  level = "primary",
  header,
  category,
  interactive = false,
  onClick,
}: SectionCardProps) {
  const classes = [
    "norgoth-section-card",
    level === "primary"
      ? "norgoth-section-card-primary"
      : "norgoth-section-card-secondary",
    interactive ? "norgoth-card-interactive" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const style = category
    ? ({ ["--norgoth-section-accent" as string]: categoryAccent(category) } as React.CSSProperties)
    : undefined;

  return (
    <CCard
      className={classes}
      style={style}
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
      {header ? <CCardHeader className="norgoth-section-card-header">{header}</CCardHeader> : null}
      <CCardBody>{children}</CCardBody>
    </CCard>
  );
}
