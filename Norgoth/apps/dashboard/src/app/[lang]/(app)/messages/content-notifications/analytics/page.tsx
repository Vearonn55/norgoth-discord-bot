import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { AnalyticsPanel } from "@/components/content-notifications/analytics-panel";
import { getDictionary, hasLocale } from "../../../../dictionaries";

export default async function AnalyticsPage({
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
        title={copy.analyticsPageTitle}
        description={copy.analyticsPageDescription}
        category="messages"
      />
      <AnalyticsPanel />
    </div>
  );
}
