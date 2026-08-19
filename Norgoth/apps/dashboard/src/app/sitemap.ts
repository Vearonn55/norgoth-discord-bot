import type { MetadataRoute } from "next";
import { getDashboardOrigin } from "@/lib/dashboard-origin";

export default function sitemap(): MetadataRoute.Sitemap {
  const origin = getDashboardOrigin();
  return [
    {
      url: `${origin}/en`,
      lastModified: new Date(),
      alternates: { languages: { en: `${origin}/en`, tr: `${origin}/tr` } },
    },
    {
      url: `${origin}/tr`,
      lastModified: new Date(),
      alternates: { languages: { en: `${origin}/en`, tr: `${origin}/tr` } },
    },
  ];
}
