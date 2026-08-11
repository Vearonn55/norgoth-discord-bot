import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { DashboardAutoRefresh } from "@/components/dashboard/dashboard-auto-refresh";
import { CampaignArchiveToolbar } from "@/components/campaigns/campaign-archive-toolbar";
import { CampaignHistoryTable } from "@/components/campaigns/campaign-history-table";
import { hasLocale } from "../../../dictionaries";

export default async function CampaignHistoryPage({
  params,
}: PageProps<"/[lang]/campaigns/history">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  return (
    <>
      <DashboardAutoRefresh />

      <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Campaign History"
          category="campaigns"
          description="Delivery archive across all campaign executions, with status, audience, delivery metrics, and CSV export."
        />

        <CampaignArchiveToolbar />

        <CampaignHistoryTable />
      </div>
    </>
  );
}
