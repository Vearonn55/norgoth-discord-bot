import { NextRequest, NextResponse } from "next/server";
import { defaultLocale, locales, type Locale } from "@/i18n/config";
import { dashboardUrl, getDashboardOrigin } from "@/lib/dashboard-origin";

const PUBLIC_SUFFIXES = ["", "/login", "/auth/complete"];

function getLocaleFromRequest(request: NextRequest): Locale {
  const header = request.headers.get("accept-language")?.toLowerCase() ?? "";

  if (header.includes("tr")) return "tr";
  return defaultLocale;
}

function isPublicPath(pathname: string): boolean {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) return true;
  const lang = parts[0];
  if (lang !== "en" && lang !== "tr") return false;
  if (parts.length === 1) return true;
  const rest = "/" + parts.slice(1).join("/");
  if (PUBLIC_SUFFIXES.includes(rest)) return true;
  if (rest.startsWith("/tickets/transcript/")) return true;
  if (pathname.startsWith("/api/")) return true;
  if (pathname.startsWith("/norgoth-api/")) return true;
  return false;
}

function isLocaleExemptPath(pathname: string): boolean {
  return (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/norgoth-api/") ||
    pathname.startsWith("/_next/")
  );
}

/** Rewrite nextUrl to the trusted public origin before absolute redirects. */
function applyPublicOrigin(request: NextRequest): void {
  const origin = new URL(getDashboardOrigin(request.url));
  request.nextUrl.protocol = origin.protocol;
  request.nextUrl.hostname = origin.hostname;
  request.nextUrl.port = origin.port;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // App Router API routes and the API rewrite must not get a /{lang} prefix.
  if (isLocaleExemptPath(pathname)) {
    return NextResponse.next();
  }

  const pathnameHasLocale = locales.some(
    (locale) => pathname === `/${locale}` || pathname.startsWith(`/${locale}/`)
  );

  if (!pathnameHasLocale) {
    const locale = getLocaleFromRequest(request);
    applyPublicOrigin(request);
    request.nextUrl.pathname = `/${locale}${pathname}`;
    return NextResponse.redirect(request.nextUrl);
  }

  const authEnforced = process.env.NORGOTH_AUTH_ENFORCED === "true";
  const session = request.cookies.get("norgoth_session")?.value;

  if (authEnforced && !session && !isPublicPath(pathname)) {
    const lang = pathname.split("/").filter(Boolean)[0] || defaultLocale;
    return NextResponse.redirect(
      dashboardUrl(`/${lang}/login`, request.url),
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|norgoth-api|api|.*\\..*).*)"],
};
