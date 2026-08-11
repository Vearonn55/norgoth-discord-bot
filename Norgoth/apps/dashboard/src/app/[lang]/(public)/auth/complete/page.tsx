import { redirect } from "next/navigation";
import { hasLocale } from "../../../dictionaries";
import { notFound } from "next/navigation";

/** Bridges Discord OAuth exchange → HttpOnly cookie on the dashboard origin. */
export default async function AuthCompletePage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ code?: string }>;
}) {
  const { lang } = await params;
  const { code } = await searchParams;
  if (!hasLocale(lang)) notFound();
  if (!code) {
    redirect(`/${lang}/login?error=missing_code`);
  }
  redirect(`/api/auth/complete?lang=${encodeURIComponent(lang)}&code=${encodeURIComponent(code)}`);
}
