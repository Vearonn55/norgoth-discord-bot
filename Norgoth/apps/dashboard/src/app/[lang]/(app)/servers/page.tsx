import { ServerSelector } from "@/components/auth/server-selector";
import { hasLocale } from "../../dictionaries";
import { notFound } from "next/navigation";

export default async function ServersPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  return <ServerSelector />;
}
