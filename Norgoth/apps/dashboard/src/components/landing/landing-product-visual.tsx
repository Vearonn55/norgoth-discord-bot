import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingProductVisual({ copy }: { copy: LandingCopy }) {
  return (
    <div className="norgoth-landing-mock" aria-hidden="true">
      <div className="norgoth-landing-mock-sidebar">{copy.demoSidebar}</div>
      <div className="norgoth-landing-mock-main">
        <div className="norgoth-landing-mock-bar" />
        <div className="norgoth-landing-mock-tile">{copy.demoCard1}</div>
        <div className="norgoth-landing-mock-tile">{copy.demoCard2}</div>
        <div className="norgoth-landing-mock-tile">{copy.demoCard3}</div>
        <p className="mb-0 small text-body-secondary">{copy.demoDisclaimer}</p>
      </div>
    </div>
  );
}
