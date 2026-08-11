import { redirect } from "next/navigation";
import { hasLocale } from "../../../dictionaries";
import { notFound } from "next/navigation";

export default async function LegacyNotificationsRedirect({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  redirect(`/${lang}/messages/content-notifications`);
}
