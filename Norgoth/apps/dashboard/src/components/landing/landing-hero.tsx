"use client";

import { LandingCtas } from "@/components/landing/landing-ctas";
import type { LandingCopy } from "@/components/landing/landing-copy";
import { LandingMotionRoot, m, useReducedMotion } from "@/components/landing/landing-motion";
import { LandingProductVisual } from "@/components/landing/landing-product-visual";

export function LandingHero({
  copy,
  loginHref,
  inviteHref,
}: {
  copy: LandingCopy;
  loginHref: string;
  inviteHref: string;
}) {
  const reduce = useReducedMotion();
  const step = reduce ? 0 : 0.06;
  const duration = reduce ? 0 : 0.4;

  return (
    <LandingMotionRoot>
      <section className="norgoth-landing-hero py-5">
        <div className="container" style={{ maxWidth: 1100 }}>
          <div className="row g-4 align-items-center">
            <div className="col-md-7">
              <m.p
                className="mb-2 fw-bold text-uppercase"
                style={{ letterSpacing: "0.18em", color: "var(--cui-primary)" }}
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0, duration }}
              >
                {copy.heroEyebrow}
              </m.p>
              <m.h1
                className="display-5 fw-bold mb-3"
                style={{ lineHeight: 1.15, maxWidth: 640 }}
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: step, duration }}
              >
                {copy.heroTitle1}
                <br />
                {copy.heroTitle2}
                <br />
                {copy.heroTitle3}
              </m.h1>
              <m.p
                className="lead text-body-secondary mb-3"
                style={{ maxWidth: 640 }}
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: step * 2, duration }}
              >
                {copy.heroLead}
              </m.p>
              <m.div
                className="mb-3"
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: step * 3, duration }}
              >
                <LandingCtas
                  copy={copy}
                  loginHref={loginHref}
                  inviteHref={inviteHref}
                />
              </m.div>
              <m.p
                className="small text-body-secondary mb-0"
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: step * 4, duration }}
              >
                {copy.heroTrust}
              </m.p>
            </div>
            <m.div
              className="col-md-5 d-none d-md-block"
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: step * 5, duration }}
            >
              <LandingProductVisual copy={copy} />
            </m.div>
          </div>
        </div>
      </section>
    </LandingMotionRoot>
  );
}
