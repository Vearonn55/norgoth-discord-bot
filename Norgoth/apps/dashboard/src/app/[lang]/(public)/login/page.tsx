import { redirect } from "next/navigation";
import { hasLocale } from "../../dictionaries";
import { notFound } from "next/navigation";

export default async function LoginPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  // Dev bypass: when auth is not enforced, skip Discord OAuth and land directly
  // in the app. Re-enable login by setting NEXT_PUBLIC_AUTH_ENFORCED=true.
  if (process.env.NEXT_PUBLIC_AUTH_ENFORCED === "false") {
    redirect(`/${lang}/servers`);
  }

  redirect(
    `/norgoth-api/api/v1/oauth/discord/dashboard/authorize?lang=${encodeURIComponent(lang)}`
  );
}
