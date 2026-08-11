import { notFound } from "next/navigation";
import { getDictionary, hasLocale } from "../../../dictionaries";
import { FeedChannelsPanel } from "@/components/community/feed-channels-panel";

export default async function FeedChannelsPage({
  params,
}: PageProps<"/[lang]/community/feed-channels">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return <FeedChannelsPanel />;
}
