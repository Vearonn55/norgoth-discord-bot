import { notFound } from "next/navigation";
import { cilImage } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
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
        title="Embed Library"
        icon={<Icon icon={cilImage} size="xl" />}
        description="Create, save, and reuse Discord embed drafts. Deploy them to channels and re-sync previously deployed messages after editing."
        category="messages"
        infoKey="embedMessages"
      />
      <EmbedMessagesPanel lang={lang} />
    </div>
  );
}
