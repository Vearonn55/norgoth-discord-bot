import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { EmbedMessagesPanel } from "@/components/embed-messages/embed-messages-panel";
import { hasLocale } from "../../../dictionaries";

export default async function EmbedMessagesPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Embed Messages"
        description="Create, save, and reuse Discord embed messages. Send them to channels and update previously sent messages after editing."
        category="messages"
      />
      <EmbedMessagesPanel lang={lang} />
    </div>
  );
}
