import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { DeliveryHistoryPanel } from "@/components/content-notifications/delivery-history-panel";
import { hasLocale } from "../../../../dictionaries";

export default async function HistoryPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Delivery History"
        description="Paginated notification delivery attempts for this server."
        category="messages"
      />
      <DeliveryHistoryPanel />
    </div>
  );
}
