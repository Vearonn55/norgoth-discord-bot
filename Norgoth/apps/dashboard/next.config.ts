import type { NextConfig } from "next";

const apiOrigin =
  process.env.NORGOTH_API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "192.168.137.114",
    "127.0.0.1",
    "localhost",
  ],
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
