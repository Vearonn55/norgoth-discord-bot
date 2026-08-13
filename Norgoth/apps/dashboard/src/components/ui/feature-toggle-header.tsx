"use client";

import type { ReactNode } from "react";
import { Switch } from "@/components/ui/switch";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

type FeatureToggleHeaderProps = {
  title: string;
  description?: ReactNode;
  enabled: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  id?: string;
  /** Optional trailing content rendered left of the switch (e.g. a badge). */
  aside?: ReactNode;
  headingLevel?: "h2" | "h3";
};

/**
 * Standard Norgoth feature-toggle pattern: the main enable/disable switch sits
 * next to the feature title rather than in a separate lower card.
 */
export function FeatureToggleHeader({
  title,
  description,
  enabled,
  onChange,
  disabled = false,
  id,
  aside,
  headingLevel = "h2",
}: FeatureToggleHeaderProps) {
  const dict = useLocaleDict();
  const Heading = headingLevel;
  return (
    <div className="d-flex align-items-start justify-content-between gap-3">
      <div className="min-w-0">
        <Heading className="h5 mb-0 fw-semibold">{title}</Heading>
        {description ? (
          <p className="mb-0 mt-1 small text-body-secondary">{description}</p>
        ) : null}
      </div>
      <div className="d-flex align-items-center gap-2 flex-shrink-0">
        {aside}
        <span
          className="small"
          style={{ color: enabled ? "var(--cui-success)" : "var(--cui-secondary)" }}
        >
          {enabled ? dict.common.enabled : dict.common.disabled}
        </span>
        <Switch
          id={id}
          size="lg"
          checked={enabled}
          disabled={disabled}
          onChange={onChange}
          aria-label={formatDict(dict.common.toggleNamed, { name: title })}
        />
      </div>
    </div>
  );
}
