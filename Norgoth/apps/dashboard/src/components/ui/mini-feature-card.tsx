"use client";

import type { CSSProperties } from "react";
import { Icon } from "@/components/ui/icon";
import { Switch } from "@/components/ui/switch";
import type { NorgothCategory } from "@/lib/design/category";
import { categoryAccent } from "@/lib/design/category";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

export type MiniFeatureStatus =
  | "enabled"
  | "disabled"
  | "configured"
  | "needs-attention"
  | "neutral";

const STATUS_COLORS: Record<MiniFeatureStatus, string> = {
  enabled: "var(--cui-success)",
  disabled: "var(--cui-secondary)",
  configured: "var(--cui-info)",
  "needs-attention": "var(--cui-warning)",
  neutral: "var(--cui-secondary)",
};

type MiniFeatureCardProps = {
  icon: string | string[];
  name: string;
  description?: string;
  category?: NorgothCategory;
  status?: MiniFeatureStatus;
  /** Overrides the default status label text. */
  statusLabel?: string;
  onClick: () => void;
  /**
   * When provided, an inline enable toggle is rendered on the card. Enabled
   * cards use a green accent (or ``enabledAccent`` when set); disabled cards
   * use ``disabledAccent`` when set (e.g. danger red), otherwise neutral.
   * The toggle text label (Enabled/Disabled) is always shown so color is not
   * the only signal.
   */
  enabled?: boolean;
  onToggle?: (checked: boolean) => void;
  toggleDisabled?: boolean;
  /**
   * When set with a toggle, used as the left/icon accent while enabled instead
   * of the default success green (e.g. Discord Logs category colours).
   */
  enabledAccent?: string;
  /**
   * Accent used while the toggle is off. Prefer danger red when a parent
   * master switch is on so disabled services read as intentionally off.
   */
  disabledAccent?: string;
};

/**
 * Compact, dense feature card. Shows an icon, name, short description and a
 * status dot/badge, and opens a configuration modal on click. Category color
 * drives the accent unless an enable toggle is present, in which case the
 * accent becomes green (or ``enabledAccent``) when enabled and neutral when
 * disabled.
 */
export function MiniFeatureCard({
  icon,
  name,
  description,
  category,
  status = "neutral",
  statusLabel,
  onClick,
  enabled,
  onToggle,
  toggleDisabled = false,
  enabledAccent,
  disabledAccent,
}: MiniFeatureCardProps) {
  const dict = useLocaleDict();
  const statusLabels: Record<MiniFeatureStatus, string> = {
    enabled: dict.common.enabled,
    disabled: dict.common.disabled,
    configured: dict.common.configured,
    "needs-attention": dict.common.needsAttention,
    neutral: "",
  };
  const hasToggle = typeof onToggle === "function";
  const categoryColor = category ? categoryAccent(category) : undefined;
  const onAccent = enabledAccent || "var(--cui-success)";
  const offAccent = disabledAccent || "rgba(241, 244, 250, 0.28)";
  const offText = disabledAccent || "var(--cui-secondary)";
  const accent = hasToggle
    ? enabled
      ? onAccent
      : offAccent
    : categoryColor;

  const iconColor = hasToggle
    ? enabled
      ? onAccent
      : offText
    : categoryColor;

  const label = statusLabel ?? statusLabels[status];
  const accentStyle = accent
    ? ({ ["--norgoth-section-accent" as string]: accent } as CSSProperties)
    : undefined;

  const body = (
    <>
      <span
        className="norgoth-mini-card-icon flex-shrink-0 d-inline-flex align-items-center justify-content-center"
        style={iconColor ? { color: iconColor, borderColor: accent } : undefined}
        aria-hidden
      >
        <Icon icon={icon} height={20} />
      </span>
      <span className="min-w-0 flex-grow-1">
        <span className="d-flex align-items-center justify-content-between gap-2">
          <span className="fw-semibold text-white text-truncate">{name}</span>
          {!hasToggle && label ? (
            <span className="norgoth-mini-card-status small d-inline-flex align-items-center gap-1 flex-shrink-0">
              <span
                className="norgoth-mini-card-dot"
                style={{ background: STATUS_COLORS[status] }}
                aria-hidden
              />
              {label}
            </span>
          ) : null}
        </span>
        {description ? (
          <span className="norgoth-mini-card-description d-block small text-body-secondary mt-1">
            {description}
          </span>
        ) : null}
      </span>
    </>
  );

  if (!hasToggle) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="norgoth-mini-card text-start w-100 h-100 d-flex align-items-start gap-3 p-3"
        style={accentStyle}
      >
        {body}
      </button>
    );
  }

  return (
    <div
      className="norgoth-mini-card h-100 d-flex align-items-start gap-3 p-3"
      style={accentStyle}
    >
      <button
        type="button"
        onClick={onClick}
        className="norgoth-mini-card-hit"
        aria-label={formatDict(dict.common.configureAria, { name })}
      >
        {body}
      </button>
      <span className="norgoth-mini-card-toggle">
        <span
          className="small flex-shrink-0"
          style={{
            color: enabled ? onAccent : offText,
          }}
        >
          {statusLabel ??
            (enabled ? dict.common.enabled : dict.common.disabled)}
        </span>
        <Switch
          checked={!!enabled}
          disabled={toggleDisabled}
          onChange={(checked) => onToggle?.(checked)}
          aria-label={formatDict(dict.common.toggleAria, { name })}
        />
      </span>
    </div>
  );
}
