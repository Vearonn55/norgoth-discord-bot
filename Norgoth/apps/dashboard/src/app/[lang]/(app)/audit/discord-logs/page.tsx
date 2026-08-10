import { Suspense } from "react";
import { notFound } from "next/navigation";
import { DiscordLogsPage } from "@/components/audit/discord-logs-page";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function DiscordLogsRoute({
  params,
}: PageProps<"/[lang]/audit/discord-logs">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <Suspense fallback={null}>
      <DiscordLogsPage />
    </Suspense>
  );
}
