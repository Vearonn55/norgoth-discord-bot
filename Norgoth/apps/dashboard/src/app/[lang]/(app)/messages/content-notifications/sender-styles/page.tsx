import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { SenderStylesPanel } from "@/components/content-notifications/sender-styles-panel";
import { getDictionary, hasLocale } from "../../../../dictionaries";

export default async function SenderStylesPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const copy = dict.contentNotifications;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={copy.stylesPageTitle}
        description={copy.stylesPageDescription}
        category="messages"
      />
      <SenderStylesPanel />
    </div>
  );
}
