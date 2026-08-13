import { notFound } from "next/navigation";
import { cilImage } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { EmbedMessagesPanel } from "@/components/embed-messages/embed-messages-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function EmbedMessagesPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const info = dict.featureInfo.embedMessages;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info.title}
        icon={<Icon icon={cilImage} size="xl" />}
        description={info.description}
        category="messages"
        infoKey="embedMessages"
      />
      <EmbedMessagesPanel lang={lang} />
    </div>
  );
}
