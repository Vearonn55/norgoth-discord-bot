import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { EmbedMessageEditor } from "@/components/embed-messages/embed-message-editor";
import { getDictionary, hasLocale } from "../../../../dictionaries";

export default async function EmbedMessageEditorPage({
  params,
}: {
  params: Promise<{ lang: string; id: string }>;
}) {
  const { lang, id } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const info = dict.featureInfo.embedMessages;
  const isNew = id === "new";

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={isNew ? info.newTitle : info.editTitle}
        description={info.editDescription}
        category="messages"
      />
      <EmbedMessageEditor lang={lang} messageId={id} />
    </div>
  );
}
