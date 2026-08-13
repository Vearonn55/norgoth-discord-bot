import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { DeliveryHistoryPanel } from "@/components/content-notifications/delivery-history-panel";
import { getDictionary, hasLocale } from "../../../../dictionaries";

export default async function HistoryPage({
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
        title={copy.historyPageTitle}
        description={copy.historyPageDescription}
        category="messages"
      />
      <DeliveryHistoryPanel />
    </div>
  );
}
