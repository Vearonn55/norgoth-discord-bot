import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { EmbedMessageEditor } from "@/components/embed-messages/embed-message-editor";
import { hasLocale } from "../../../../dictionaries";

export default async function EmbedMessageEditorPage({
  params,
}: {
  params: Promise<{ lang: string; id: string }>;
}) {
  const { lang, id } = await params;
  if (!hasLocale(lang)) notFound();

  const isNew = id === "new";

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={isNew ? "New Embed" : "Edit Embed"}
        description="Design the reusable embed content and preview it live. Deploy and re-sync from the Embed Library."
        category="messages"
      />
      <EmbedMessageEditor lang={lang} messageId={id} />
    </div>
  );
}
