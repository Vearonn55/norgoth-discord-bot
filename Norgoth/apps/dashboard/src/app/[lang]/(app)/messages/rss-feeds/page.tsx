import { notFound } from "next/navigation";
import { RssFeedsPanel } from "@/components/messages/rss-feeds-panel";
import { hasLocale } from "../../../dictionaries";

export default async function RssFeedsPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  return <RssFeedsPanel />;
}
