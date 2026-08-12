"use client";

import type { ReactNode } from "react";
import { useInViewOnce } from "@/hooks/use-in-view-once";

export function LandingSection({
  id,
  children,
  className,
}: {
  id?: string;
  children: ReactNode;
  className?: string;
}) {
  const { ref, inView } = useInViewOnce<HTMLElement>();
  const classes = [
    "norgoth-landing-section norgoth-landing-reveal",
    inView ? "is-visible" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section id={id} ref={ref} className={classes}>
      {children}
    </section>
  );
}
