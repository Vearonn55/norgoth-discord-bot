"use client";

import { LazyMotion, domAnimation, m, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

export function LandingMotionRoot({ children }: { children: ReactNode }) {
  return <LazyMotion features={domAnimation}>{children}</LazyMotion>;
}

export { m, useReducedMotion };
