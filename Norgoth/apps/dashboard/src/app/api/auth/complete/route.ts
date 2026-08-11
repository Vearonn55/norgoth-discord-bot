import { NextRequest, NextResponse } from "next/server";
import { dashboardUrl } from "@/lib/dashboard-origin";

const COOKIE_NAME = "norgoth_session";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const lang = request.nextUrl.searchParams.get("lang") || "en";

  if (!code) {
    return NextResponse.redirect(
      dashboardUrl(`/${lang}/login?error=missing_code`, request.url),
    );
  }

  const apiOrigin =
    process.env.NORGOTH_API_INTERNAL_URL?.trim() || "http://127.0.0.1:8000";

  const exchange = await fetch(`${apiOrigin}/api/v1/sessions/exchange`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
    cache: "no-store",
  });

  if (!exchange.ok) {
    return NextResponse.redirect(
      dashboardUrl(`/${lang}/login?error=exchange`, request.url),
    );
  }

  // Prefer session id from API Set-Cookie if present; else from body.
  let sessionId: string | null = null;
  const setCookie = exchange.headers.getSetCookie?.() ?? [];
  for (const raw of setCookie) {
    if (raw.startsWith(`${COOKIE_NAME}=`)) {
      sessionId = raw.split(";", 1)[0].slice(COOKIE_NAME.length + 1);
      break;
    }
  }

  if (!sessionId) {
    const payload = (await exchange.json()) as {
      user?: { session_id?: string };
    };
    sessionId = payload.user?.session_id ?? null;
  }

  if (!sessionId) {
    return NextResponse.redirect(
      dashboardUrl(`/${lang}/login?error=session`, request.url),
    );
  }

  const response = NextResponse.redirect(
    dashboardUrl(`/${lang}/servers`, request.url),
  );
  response.cookies.set({
    name: COOKIE_NAME,
    value: sessionId,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return response;
}
