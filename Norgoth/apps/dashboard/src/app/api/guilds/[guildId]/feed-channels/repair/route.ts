import { NextRequest, NextResponse } from "next/server";

/**
 * Long-running Top Trending repair must not go through Next rewrite proxy
 * (≈30s hang-up). This route handler proxies directly to the API.
 */
export const maxDuration = 300;
export const dynamic = "force-dynamic";

const REPAIR_TIMEOUT_MS = 280_000;

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ guildId: string }> },
) {
  const { guildId } = await context.params;
  if (!/^[0-9]{5,25}$/.test(guildId)) {
    return NextResponse.json({ detail: "Invalid guild id." }, { status: 400 });
  }

  const apiOrigin =
    process.env.NORGOTH_API_INTERNAL_URL?.trim() || "http://127.0.0.1:8000";

  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) {
    headers.cookie = cookie;
  }
  const authorization = request.headers.get("authorization");
  if (authorization) {
    headers.authorization = authorization;
  }

  let upstream: Response;
  try {
    upstream = await fetch(
      `${apiOrigin}/guilds/${guildId}/feed-channels/repair`,
      {
        method: "POST",
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(REPAIR_TIMEOUT_MS),
      },
    );
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Upstream repair request failed.";
    return NextResponse.json(
      { detail: `Top Trending repair proxy failed: ${message}` },
      { status: 504 },
    );
  }

  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type":
        upstream.headers.get("content-type") ?? "application/json",
    },
  });
}
