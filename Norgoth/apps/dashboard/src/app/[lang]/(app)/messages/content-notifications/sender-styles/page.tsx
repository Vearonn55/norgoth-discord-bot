import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { SenderStylesPanel } from "@/components/content-notifications/sender-styles-panel";
import { hasLocale } from "../../../../dictionaries";

export default async function SenderStylesPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Sender Styles"
        description="Optional webhook display name and avatar overrides."
        category="messages"
      />
      <SenderStylesPanel />
    </div>
  );
}
