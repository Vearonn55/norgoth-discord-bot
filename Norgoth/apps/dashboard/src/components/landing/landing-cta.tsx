import { LandingCtas } from "@/components/landing/landing-ctas";
import { LandingSection } from "@/components/landing/landing-section";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingCta({
  copy,
  loginHref,
  inviteHref,
}: {
  copy: LandingCopy;
  loginHref: string;
  inviteHref: string;
}) {
  return (
    <LandingSection className="border-top border-secondary-subtle">
      <div className="container text-center" style={{ maxWidth: 1100 }}>
        <h2 className="h3 mb-3">{copy.ctaTitle}</h2>
        <p
          className="text-body-secondary mb-4 mx-auto"
          style={{ maxWidth: 520 }}
        >
          {copy.ctaLead}
        </p>
        <div className="d-flex justify-content-center">
          <LandingCtas
            copy={copy}
            loginHref={loginHref}
            inviteHref={inviteHref}
          />
        </div>
      </div>
    </LandingSection>
  );
}
