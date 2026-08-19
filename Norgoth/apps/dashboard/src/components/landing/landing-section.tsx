"use client";

import type { ReactNode } from "react";
import { LandingMotionRoot, m, useReducedMotion } from "@/components/landing/landing-motion";

export function LandingSection({
  id,
  children,
  className,
}: {
  id?: string;
  children: ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const classes = ["norgoth-landing-section", className ?? ""]
    .filter(Boolean)
    .join(" ");

  return (
    <LandingMotionRoot>
      <m.section
        id={id}
        className={classes}
        initial={reduce ? false : { opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.15 }}
        transition={{ duration: reduce ? 0 : 0.45, ease: "easeOut" }}
      >
        {children}
      </m.section>
    </LandingMotionRoot>
  );
}
