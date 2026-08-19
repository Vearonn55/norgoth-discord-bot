"use client";

import { useState } from "react";
import { LandingCtas } from "@/components/landing/landing-ctas";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingMobileNav({
  copy,
  loginHref,
  inviteHref,
}: {
  copy: LandingCopy;
  loginHref: string;
  inviteHref: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = "landing-mobile-nav";

  return (
    <div className="d-md-none">
      <button
        type="button"
        className="btn btn-outline-light"
        style={{ minHeight: 40, minWidth: 40 }}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? copy.navClose : copy.navMenu}
      </button>
      {open ? (
        <div
          id={panelId}
          className="position-absolute start-0 end-0 mt-2 px-3 pb-3"
          style={{
            background: "rgba(11, 14, 20, 0.97)",
            borderBottom: "1px solid var(--norgoth-card-border-secondary)",
          }}
        >
          <nav className="d-flex flex-column gap-2 py-3 small">
            <a href="#features" className="text-decoration-none text-body" onClick={() => setOpen(false)}>
              {copy.navFeatures}
            </a>
            <a href="#why" className="text-decoration-none text-body" onClick={() => setOpen(false)}>
              {copy.navWhy}
            </a>
            <a href="#how-it-works" className="text-decoration-none text-body" onClick={() => setOpen(false)}>
              {copy.navHow}
            </a>
            <a href="#trust" className="text-decoration-none text-body" onClick={() => setOpen(false)}>
              {copy.navTrust}
            </a>
          </nav>
          <LandingCtas
            copy={copy}
            loginHref={loginHref}
            inviteHref={inviteHref}
            size="md"
          />
        </div>
      ) : null}
    </div>
  );
}
