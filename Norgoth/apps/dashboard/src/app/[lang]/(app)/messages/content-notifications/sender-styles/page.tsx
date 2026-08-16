import { notFound, redirect } from "next/navigation";
import { hasLocale } from "../../../../dictionaries";

export default async function SenderStylesRedirectPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  redirect(`/${lang}/messages/content-notifications?panel=sender-styles`);
}
