import { notFound } from "next/navigation";
import { AutomodPanel } from "@/components/security/automod-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function AutoModerationPage({
  params,
}: PageProps<"/[lang]/security/auto-moderation">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return <AutomodPanel />;
}
