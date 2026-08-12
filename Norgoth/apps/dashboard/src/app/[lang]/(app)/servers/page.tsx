import { ServerSelector } from "@/components/auth/server-selector";
import { getDictionary, hasLocale } from "../../dictionaries";
import { notFound } from "next/navigation";

export default async function ServersPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  return <ServerSelector copy={dict.servers} />;
}
