import type { MetadataRoute } from "next";
import { getDashboardOrigin } from "@/lib/dashboard-origin";

export default function robots(): MetadataRoute.Robots {
  const origin = getDashboardOrigin();
  return {
    rules: { userAgent: "*", allow: ["/", "/en", "/tr"] },
    sitemap: `${origin}/sitemap.xml`,
  };
}
