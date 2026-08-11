import Link from "next/link";
import { notFound } from "next/navigation";
import { cilHeart } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { DashboardAutoRefresh } from "@/components/dashboard/dashboard-auto-refresh";
import { WorkerHealthPanel } from "@/components/dashboard/worker-health-panel";
import { WorkerHeartbeatHistory } from "@/components/dashboard/worker-heartbeat-history";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function WorkerHealthPage({
  params,
}: PageProps<"/[lang]/observability/worker-health">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <>
      <DashboardAutoRefresh />

      <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Worker Health"
          icon={<Icon icon={cilHeart} size="xl" />}
          description="Campaign worker heartbeat and delivery liveness, straight from Redis."
          actions={
            <Button asChild variant="secondary">
              <Link href={`/${lang}/campaigns/history`}>Campaign History</Link>
            </Button>
          }
        />

        <section>
          <WorkerHealthPanel />
        </section>

        <section>
          <WorkerHeartbeatHistory />
        </section>
      </div>
    </>
  );
}
