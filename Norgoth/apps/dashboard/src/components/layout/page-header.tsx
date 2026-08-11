import type { ReactNode } from "react";
import type { NorgothCategory } from "@/lib/design/category";
import { categoryAccent } from "@/lib/design/category";
import { HeaderMasterToggle } from "@/components/layout/header-master-toggle";
import { FeatureInfo } from "@/components/ui/feature-info";
import type { FeatureInfoContent, FeatureInfoKey } from "@/lib/feature-info";

export type PageHeaderMasterToggle = {
  enabled: boolean;
  onChange: (checked: boolean) => void;
  loading?: boolean;
  label?: string;
  showLabel?: boolean;
};

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  icon?: ReactNode;
  category?: NorgothCategory;
  /**
   * Page-level master enable/disable switch, rendered on the right of the
   * header. Use for main features that have a true page-level enabled state.
   */
  masterToggle?: PageHeaderMasterToggle;
  /**
   * Feature-level contextual help. Provide `infoKey` to resolve localized
   * content from the `featureInfo` dictionary, or pass `info` directly. An
   * accessible info icon + popover renders beside the title.
   */
  infoKey?: FeatureInfoKey | string;
  info?: FeatureInfoContent;
};

export function PageHeader({
  title,
  description,
  actions,
  icon,
  category,
  masterToggle,
  infoKey,
  info,
}: PageHeaderProps) {
  return (
    <header
      className="norgoth-page-header d-flex flex-column flex-xl-row align-items-xl-end justify-content-xl-between gap-3 mb-4 pb-3 border-bottom"
      style={
        category
          ? { borderBottomColor: categoryAccent(category) }
          : undefined
      }
      data-category={category}
    >
      <div className="mw-100" style={{ maxWidth: 52 * 16 }}>
        <div className="d-flex align-items-center gap-3">
          {icon ? (
            <div
              className="norgoth-page-icon"
              style={
                category ? { color: categoryAccent(category) } : undefined
              }
            >
              {icon}
            </div>
          ) : null}
          <h1 className="h2 mb-0 fw-semibold">{title}</h1>
          {infoKey || info ? (
            <FeatureInfo featureKey={infoKey} content={info ?? null} />
          ) : null}
        </div>
        {description ? (
          <p className="text-body-secondary mt-2 mb-0" style={{ maxWidth: 42 * 16 }}>
            {description}
          </p>
        ) : null}
      </div>

      {actions || masterToggle ? (
        <div className="d-flex flex-wrap align-items-center gap-3 justify-content-xl-end">
          {actions}
          {masterToggle ? (
            <HeaderMasterToggle
              enabled={masterToggle.enabled}
              onChange={masterToggle.onChange}
              loading={masterToggle.loading}
              label={masterToggle.label}
              showLabel={masterToggle.showLabel}
            />
          ) : null}
        </div>
      ) : null}
    </header>
  );
}
