"use client";

import type { CSSProperties, HTMLAttributes, ReactNode } from "react";

/**
 * Props applied to a container to visually mute a feature's configuration body
 * when its master switch is off. The config state is never cleared — it is only
 * dimmed and made non-interactive so the user can re-enable without data loss.
 */
export type FeatureMutingProps = {
  style?: CSSProperties;
  "aria-disabled"?: boolean;
  "data-muted"?: boolean;
  inert?: boolean;
};

const MUTED_STYLE: CSSProperties = {
  opacity: 0.55,
  pointerEvents: "none",
  userSelect: "none",
  transition: "opacity 150ms ease",
};

const ACTIVE_STYLE: CSSProperties = {
  transition: "opacity 150ms ease",
};

/**
 * Returns spreadable props that mute a section when `enabled` is false.
 * Pure and deterministic so it can be unit tested in isolation.
 */
export function useFeatureMuting(enabled: boolean): FeatureMutingProps {
  if (enabled) {
    return { style: ACTIVE_STYLE, "data-muted": false };
  }
  return {
    style: MUTED_STYLE,
    "aria-disabled": true,
    "data-muted": true,
    // `inert` removes the subtree from tab order + a11y tree in modern browsers.
    inert: true,
  };
}

type MutedSectionProps = HTMLAttributes<HTMLDivElement> & {
  /** When false, the children are dimmed and made non-interactive. */
  enabled: boolean;
  children: ReactNode;
};

/**
 * Wrapper that mutes its children when a feature's master switch is off.
 * Preserves the underlying config controls (they stay mounted with their
 * current values) so toggling back on restores everything.
 */
export function MutedSection({
  enabled,
  children,
  style,
  ...rest
}: MutedSectionProps) {
  const muting = useFeatureMuting(enabled);
  return (
    <div {...rest} {...muting} style={{ ...muting.style, ...style }}>
      {children}
    </div>
  );
}
