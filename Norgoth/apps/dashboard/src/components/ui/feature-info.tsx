"use client";

import { CPopover } from "@coreui/react";
import { cilInfo } from "@coreui/icons";
import { Icon } from "@/components/ui/icon";
import {
  useFeatureInfo,
  type FeatureInfoContent,
  type FeatureInfoKey,
} from "@/lib/feature-info";

type FeatureInfoProps = {
  /** Dictionary key under the `featureInfo` namespace. */
  featureKey?: FeatureInfoKey | string;
  /** Pre-resolved content, overrides `featureKey` when provided. */
  content?: FeatureInfoContent | null;
};

/**
 * Small, accessible info affordance shown beside a feature title. Opens on
 * hover and keyboard focus, rendering a compact popover with a title, a short
 * description, and optional usage guidance. Renders nothing when no content
 * resolves, so it is safe to place unconditionally in shared headers.
 */
export function FeatureInfo({ featureKey, content }: FeatureInfoProps) {
  const resolved = useFeatureInfo(featureKey);
  const info = content ?? resolved;

  if (!info) return null;

  const popoverBody = (
    <div className="small">
      <p className="mb-0 text-body-secondary">{info.description}</p>
      {info.usage ? (
        <p className="mt-2 mb-0 text-body-secondary">{info.usage}</p>
      ) : null}
    </div>
  );

  return (
    <CPopover
      title={info.title}
      content={popoverBody}
      placement="bottom"
      trigger={["hover", "focus"]}
    >
      <button
        type="button"
        className="btn btn-link p-0 d-inline-flex align-items-center text-body-secondary"
        aria-label={`${info.title} — feature information`}
        style={{ lineHeight: 1 }}
      >
        <Icon icon={cilInfo} size="lg" />
      </button>
    </CPopover>
  );
}
