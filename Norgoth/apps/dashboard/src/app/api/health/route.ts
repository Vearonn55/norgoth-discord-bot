import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({
    status: "ok",
    service: "norbot-web",
    release_sha: process.env.NORGOTH_RELEASE_SHA ?? null,
  });
}
