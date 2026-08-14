import type { NextConfig } from "next";

const apiOrigin =
  process.env.NORGOTH_API_INTERNAL_URL ?? "http://127.0.0.1:8000";

// Detected LAN host is injected by scripts/dev.sh so cross-origin dev
// requests from other devices keep working across IP changes.
const lanHost = process.env.NORGOTH_LAN_HOST?.trim();

const nextConfig: NextConfig = {
  // Hide the floating Next.js route/config indicator in development.
  devIndicators: false,
  // Required for the production Docker image (standalone server.js).
  output: "standalone",
  allowedDevOrigins: [
    ...(lanHost ? [lanHost] : []),
    "127.0.0.1",
    "localhost",
  ],
  // Long-running proxied API calls (e.g. Top Trending repair). Prefer the
  // dedicated /api/guilds/.../repair route; this covers other rewrites.
  experimental: {
    proxyTimeout: 300_000,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), geolocation=(), microphone=()",
          },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
          },
        ],
      },
    ];
  },
  // Proxy API through the dashboard so LAN clients only need port 3000.
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: "/norgoth-api/:path*",
          destination: `${apiOrigin}/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
