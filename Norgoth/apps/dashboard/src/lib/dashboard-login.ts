import { browserApiUrl } from "@/lib/api";

/** Discord OAuth login for the Command Center, or servers when auth is bypassed. */
export function dashboardLoginHref(lang: string): string {
  const authBypassed = process.env.NEXT_PUBLIC_AUTH_ENFORCED === "false";
  if (authBypassed) {
    return `/${lang}/servers`;
  }
  return browserApiUrl(
    `/api/v1/oauth/discord/dashboard/authorize?lang=${encodeURIComponent(lang)}`,
  );
}
