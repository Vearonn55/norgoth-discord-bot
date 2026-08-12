"use client";

import { usePathname } from "next/navigation";
import { CContainer } from "@coreui/react";
import Sidebar from "@/components/navigation/sidebar";
import { Topbar } from "@/components/navigation/topbar";
import { CommandPalette } from "@/components/navigation/command-palette";
import type { Dictionary } from "@/app/[lang]/dictionaries";
import type { Locale } from "@/i18n/config";
import type { ReactNode } from "react";

type AppShellProps = {
  lang: Locale;
  dict: Dictionary;
  children: ReactNode;
};

function isTranscriptPortal(pathname: string | null): boolean {
  if (!pathname) return false;
  return /\/tickets\/transcript\//.test(pathname);
}

function isServerSelector(pathname: string | null): boolean {
  if (!pathname) return false;
  return /\/servers\/?$/.test(pathname);
}

export function AppShell({ lang, dict, children }: AppShellProps) {
  const pathname = usePathname();

  // Pre–Command-Center: no sidebar / topbar until a guild is selected.
  if (isServerSelector(pathname)) {
    return <div className="norgoth-server-selector min-vh-100">{children}</div>;
  }

  if (isTranscriptPortal(pathname)) {
    return (
      <div className="norgoth-transcript-portal min-vh-100">
        <CContainer className="py-4" style={{ maxWidth: 900 }}>
          {children}
        </CContainer>
      </div>
    );
  }

  return (
    <div className="norgoth-app d-flex">
      <Sidebar lang={lang} dict={dict} />

      <div className="norgoth-main">
        <Topbar lang={lang} dict={dict} />
        <CommandPalette lang={lang} />

        <div className="norgoth-main-body norgoth-scrollbar">
          <CContainer fluid className="px-4 py-4" style={{ maxWidth: 1600 }}>
            {children}
          </CContainer>
        </div>
      </div>
    </div>
  );
}
