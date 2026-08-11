import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { AnalyticsPanel } from "@/components/content-notifications/analytics-panel";
import { hasLocale } from "../../../../dictionaries";

export default async function AnalyticsPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Content Notification Analytics"
        description="Delivery success, latency, and platform distribution."
        category="messages"
      />
      <AnalyticsPanel />
    </div>
  );
}
