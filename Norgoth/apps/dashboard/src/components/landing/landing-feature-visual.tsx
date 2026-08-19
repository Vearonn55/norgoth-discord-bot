import type { LandingFeatureCopy } from "@/components/landing/landing-copy";

export function LandingFeatureVisual({
  groupLabel,
  feature,
}: {
  groupLabel: string;
  feature: LandingFeatureCopy;
}) {
  return (
    <div className="norgoth-landing-mock norgoth-landing-mock-feature" aria-hidden="true">
      <div className="norgoth-landing-mock-badge">{groupLabel}</div>
      <div className="norgoth-landing-mock-bar" />
      <div className="norgoth-landing-mock-tile">{feature.cap1}</div>
      <div className="norgoth-landing-mock-tile">{feature.cap2}</div>
      <div className="norgoth-landing-mock-tile">{feature.cap3}</div>
    </div>
  );
}
