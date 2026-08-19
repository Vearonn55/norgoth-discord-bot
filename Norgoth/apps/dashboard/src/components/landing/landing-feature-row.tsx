"use client";

import type { LandingCopy } from "@/components/landing/landing-copy";
import type { LandingFeatureId } from "@/components/landing/landing-feature-catalog";
import { landingFeatureDef } from "@/components/landing/landing-feature-catalog";
import { LandingMotionRoot, m, useReducedMotion } from "@/components/landing/landing-motion";
import { CATEGORY_TOKENS } from "@/lib/design/category";

export function LandingFeatureRow({
  id,
  copy,
  index,
}: {
  id: LandingFeatureId;
  copy: LandingCopy;
  index: number;
}) {
  const reduce = useReducedMotion();
  const def = landingFeatureDef(id);
  const feature = copy.features[id];
  const even = index % 2 === 1;
  const tokens = CATEGORY_TOKENS[def.category];
  const offset = reduce ? 0 : even ? 28 : -28;

  return (
    <LandingMotionRoot>
      <m.article
        className={`norgoth-landing-feature-row mb-5${even ? " is-even" : ""}`}
        style={{ ["--norgoth-section-accent" as string]: `var(${tokens.cssVar})` }}
        initial={reduce ? false : { opacity: 0, x: offset }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true, amount: 0.15 }}
        transition={{ duration: reduce ? 0 : 0.5, ease: "easeOut" }}
      >
        <div className="norgoth-landing-feature-copy">
          <p
            className="small text-uppercase fw-bold mb-2"
            style={{ letterSpacing: "0.08em", color: tokens.color }}
          >
            {tokens.label}
          </p>
          <h3 className="h4">{feature.title}</h3>
          <p className="text-body-secondary">{feature.summary}</p>
          <p>{feature.body}</p>
          <ul className="mb-0 ps-3">
            <li>{feature.cap1}</li>
            <li>{feature.cap2}</li>
            <li>{feature.cap3}</li>
          </ul>
        </div>
        <div className="norgoth-landing-feature-visual" aria-hidden="true">
          <div className="norgoth-landing-mock">
            <div className="norgoth-landing-mock-sidebar">{copy.demoSidebar}</div>
            <div className="norgoth-landing-mock-main">
              <div className="norgoth-landing-mock-bar" />
              <div className="norgoth-landing-mock-tile">{feature.cap1}</div>
              <div className="norgoth-landing-mock-tile">{feature.cap2}</div>
              <div className="norgoth-landing-mock-tile">{feature.cap3}</div>
            </div>
          </div>
        </div>
      </m.article>
    </LandingMotionRoot>
  );
}
